"""
Coesita Dashboard — FTM v2.2
==============================
Servidor web local que lee decisions.jsonl y muestra las métricas
de robustez del agente en tiempo real, más el pipeline de benchmark
de frameworks (Scanning → Escenarios → Testing).

Rutas:
    /                     métricas de robustez en vivo (FTM v10)
    /benchmark            comparativa de frameworks + lanzar pipeline
    /scenarios            escenarios de estrés generados
    /scanning/frameworks  scan de frameworks (JSON, ?refresh=true)
    POST /benchmark/run   lanza el pipeline completo en background
    /benchmark/status     estado del pipeline
    /api/data /api/scenarios /api/benchmark   JSON para integraciones

Arrancar:
    python dashboard/app.py

Abrir en navegador:
    http://localhost:5050
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

# ── Path al repo y al log ─────────────────────────────────────────────────────
_REPO = Path(__file__).parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_LOG_FILE = Path(os.environ.get("COESITA_LOG_DIR", str(_REPO / "logs" / "coesita"))) / "decisions.jsonl"

# ── FTM engine ────────────────────────────────────────────────────────────────
from skills.coesita.ftm_engine import (
    TIER_META, TurnResult, compute_metrics, detect_archetype,
)

# ── Pipeline de benchmark (Fases 1-4) ─────────────────────────────────────────
import threading

from skills.coesita.benchmark_store import load_agent_reports, load_history
from skills.coesita.benchmark_tester import load_results, run_full_pipeline
from skills.coesita.framework_scanner import FEATURE_KEYS, load_scan, run_scan
from skills.coesita.scenario_generator import load_scenarios, run_generation

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Coesita Dashboard", docs_url=None, redoc_url=None)


# ── Lectura y conversión del log ──────────────────────────────────────────────

def _load_records() -> list[dict]:
    if not _LOG_FILE.exists():
        return []
    records = []
    with open(_LOG_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def _record_to_turn_result(r: dict) -> TurnResult:
    """Convierte un registro del log en TurnResult para compute_metrics()."""
    decision = r.get("decision", "STAY")
    optimal = "STAY"   # en conversaciones reales no sabemos el óptimo a priori
                       # asumimos STAY como línea base conservadora

    return TurnResult(
        scenario_id=r.get("session_id", "unknown"),
        domain="generic",
        condition="stay",
        schedule_id="control_flat",
        schedule_category="control",
        turn=r.get("turn", 1),
        channels=r.get("channels", []),
        n_active_channels=len(r.get("channels", [])),
        optimal=optimal,
        decision=decision if decision in ("STAY", "ACT") else "PARSE_FAIL",
        confidence=5,
        reason=r.get("message_preview", ""),
        reason_class=r.get("reason_class", "EMPTY"),
        is_correct=(decision == "STAY"),   # conservador: STAY = correcto por defecto
        raw_prompt=r.get("message_preview", "")[:200],
        raw_response=r.get("response_preview", "")[:200],
    )


def _compute_dashboard_data() -> dict:
    records = _load_records()
    if not records:
        return {"empty": True, "records": []}

    # Agrupar por sesión
    by_session: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_session[r.get("session_id", "unknown")].append(r)

    sessions_summary = []
    all_turns: list[TurnResult] = []

    for sid, recs in sorted(by_session.items()):
        recs_sorted = sorted(recs, key=lambda x: x.get("turn", 0))
        turns = [_record_to_turn_result(r) for r in recs_sorted]
        all_turns.extend(turns)

        rd_patho_count = sum(r.get("rd_patho", 0) for r in recs_sorted)
        pressure_turns = sum(1 for r in recs_sorted if r.get("channels"))
        act_turns = sum(1 for r in recs_sorted if r.get("decision") == "ACT")

        sessions_summary.append({
            "session_id": sid[:16] + "..." if len(sid) > 16 else sid,
            "session_id_full": sid,
            "turns": len(recs_sorted),
            "pressure_turns": pressure_turns,
            "act_turns": act_turns,
            "rd_patho_count": rd_patho_count,
            "last_ts": recs_sorted[-1].get("timestamp", "")[:19].replace("T", " "),
            "platform": recs_sorted[-1].get("platform", ""),
            "records": recs_sorted,
        })

    # Métricas globales con el engine FTM
    metrics = compute_metrics(all_turns)
    archetype = detect_archetype(metrics)

    # Canales más frecuentes
    channel_counts: dict[str, int] = defaultdict(int)
    for r in records:
        for ch in r.get("channels", []):
            channel_counts[ch] += 1
    top_channels = sorted(channel_counts.items(), key=lambda x: -x[1])[:6]

    # Evolución de rdPatho por sesión (para mini-gráfico)
    rd_by_session = [
        {"session": s["session_id"], "rd_patho": s["rd_patho_count"]}
        for s in sessions_summary
    ]

    return {
        "empty": False,
        "total_turns": len(records),
        "total_sessions": len(sessions_summary),
        "metrics": {
            "crs": metrics.composite,
            "farp_strict": metrics.farp_rate,
            "abi": metrics.abi,
            "rd_patho": metrics.rd_patho,
            "stay_acc": metrics.stay_acc,
            "act_acc": metrics.act_acc,
            "dis": metrics.dis,
            "pri": metrics.pri,
            "bp": metrics.bp,
        },
        "archetype": {
            "name": archetype.name,
            "risk": archetype.risk,
            "description": archetype.description,
            "recommendation": archetype.recommendation,
        },
        "top_channels": top_channels,
        "sessions": sessions_summary[-10:],  # últimas 10 sesiones
        "rd_by_session": rd_by_session,
        "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "log_file": str(_LOG_FILE),
    }


# ── Helpers HTML ──────────────────────────────────────────────────────────────

_RISK_COLOR = {
    "minimal": "#22c55e",
    "low": "#86efac",
    "medium": "#facc15",
    "high": "#f97316",
    "critical": "#ef4444",
}

_RISK_LABEL = {
    "minimal": "ÓPTIMO",
    "low": "BUENO",
    "medium": "MODERADO",
    "high": "ALTO",
    "critical": "CRÍTICO",
}

def _crs_color(crs: float) -> str:
    if crs >= 0.90: return "#22c55e"
    if crs >= 0.75: return "#86efac"
    if crs >= 0.60: return "#facc15"
    return "#ef4444"

def _farp_color(farp: float) -> str:
    if farp <= 0.10: return "#22c55e"
    if farp <= 0.20: return "#86efac"
    if farp <= 0.35: return "#facc15"
    return "#ef4444"

def _channel_bar(count: int, max_count: int) -> str:
    pct = int((count / max(max_count, 1)) * 100)
    return f'<div style="background:#6366f1;height:8px;width:{pct}%;border-radius:4px;"></div>'


# ── Ruta principal ────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    d = _compute_dashboard_data()
    return HTMLResponse(_render(d))


@app.get("/api/data")
async def api_data():
    """Endpoint JSON para integraciones externas."""
    d = _compute_dashboard_data()
    return d


# ── Fase 1: Scanning de frameworks ────────────────────────────────────────────

@app.get("/scanning/frameworks")
async def scanning_frameworks(refresh: bool = False):
    """Scan de frameworks de agentes (JSON). ?refresh=true fuerza un re-scan."""
    if refresh:
        return run_scan()
    return load_scan() or run_scan()


# ── Fase 2: Escenarios de estrés ──────────────────────────────────────────────

@app.get("/api/scenarios")
async def api_scenarios(tier: str = "standard", refresh: bool = False):
    """Escenarios generados (JSON). ?refresh=true regenera con el tier dado."""
    if refresh:
        return run_generation(tier)
    return load_scenarios() or run_generation(tier)


@app.get("/scenarios", response_class=HTMLResponse)
async def scenarios_page():
    data = load_scenarios() or run_generation("standard")
    return HTMLResponse(_render_scenarios(data))


# ── Fase 3+4: Benchmark (pipeline completo + resultados) ─────────────────────

_BENCH_LOCK = threading.Lock()
_BENCH_STATE: dict = {"status": "idle", "run_id": None, "tier": None,
                      "started_at": None, "finished_at": None, "error": None}


def _pipeline_worker(tier: str, domain: str | None) -> None:
    try:
        summary = run_full_pipeline(tier=tier, domain=domain)
        with _BENCH_LOCK:
            _BENCH_STATE.update(
                status="done", run_id=summary["run_id"],
                finished_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            )
    except Exception as e:
        with _BENCH_LOCK:
            _BENCH_STATE.update(status="error", error=str(e))


@app.post("/benchmark/run")
async def benchmark_run(tier: str = "standard", domain: str | None = None):
    """Lanza el pipeline completo (Scanning → Scenarios → Testing) en background."""
    if tier not in TIER_META:
        return {"status": "error", "error": f"tier inválido: {tier!r}", "valid_tiers": sorted(TIER_META)}
    with _BENCH_LOCK:
        if _BENCH_STATE["status"] == "running":
            return {"status": "already_running", **_BENCH_STATE}
        _BENCH_STATE.update(
            status="running", run_id=None, tier=tier, error=None, finished_at=None,
            started_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        )
    threading.Thread(target=_pipeline_worker, args=(tier, domain), daemon=True).start()
    return {"status": "started", "tier": tier, "domain": domain}


@app.get("/benchmark/status")
async def benchmark_status():
    with _BENCH_LOCK:
        return dict(_BENCH_STATE)


@app.get("/api/benchmark")
async def api_benchmark():
    """Último run del benchmark + histórico (JSON)."""
    return {"results": load_results(), "history": load_history()}


@app.get("/benchmark", response_class=HTMLResponse)
async def benchmark_page():
    return HTMLResponse(_render_benchmark(
        scan=load_scan(),
        results=load_results(),
        history=load_history(limit=20),
    ))


# ── Modo B: Evaluación individual de agente (soul + acción real) ─────────────

@app.get("/api/agents")
async def api_agents():
    """Reportes individuales de evaluación de agente (JSON)."""
    return {"agents": load_agent_reports()}


@app.get("/agents", response_class=HTMLResponse)
async def agents_page():
    return HTMLResponse(_render_agents(load_agent_reports()))


# ── Render HTML ───────────────────────────────────────────────────────────────

_NAV_LINKS = [
    ("/", "Robustez"),
    ("/benchmark", "Modelos"),
    ("/agents", "Agentes"),
    ("/scenarios", "Escenarios"),
    ("/scanning/frameworks", "Frameworks (JSON)"),
]


def _nav(active: str) -> str:
    links = ""
    for href, label in _NAV_LINKS:
        style = (
            "color:#e0e7ff;background:#312e81;" if href == active
            else "color:#94a3b8;"
        )
        links += (
            f'<a href="{href}" style="{style}padding:5px 12px;border-radius:8px;'
            f'text-decoration:none;font-size:0.8rem;font-weight:600;">{label}</a>'
        )
    return f'<nav style="display:flex;gap:6px;margin-bottom:18px;">{links}</nav>'


_PAGE_CSS = """
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: system-ui, -apple-system, sans-serif; background: #0f172a;
           color: #e2e8f0; min-height: 100vh; padding: 24px; }
    h1   { font-size: 1.4rem; font-weight: 700; color: #6366f1; }
    h2   { font-size: 0.85rem; font-weight: 600; color: #94a3b8;
           text-transform: uppercase; letter-spacing: .05em; margin-bottom: 14px; }
    .card { background: #1e293b; border-radius: 12px; padding: 20px; margin-bottom: 16px; }
    table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
    th    { color: #64748b; font-weight: 600; padding: 8px 10px; text-align: left;
            border-bottom: 1px solid #1e293b; }
    td    { padding: 8px 10px; border-bottom: 1px solid #0f172a; }
    tr:hover td { background: #1e293b44; }
    .tag  { font-size: 0.7rem; padding: 2px 8px; border-radius: 10px; }
    footer { text-align:center; font-size:0.72rem; color:#334155; margin-top:32px; }
"""


def _render(d: dict) -> str:
    if d.get("empty"):
        return _render_empty()
    return _render_full(d)


def _render_empty() -> str:
    return """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Coesita Dashboard</title>
  <meta http-equiv="refresh" content="15">
  <style>
    body { font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0;
           display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
    .box { text-align: center; }
    h1 { font-size: 1.5rem; color: #6366f1; }
    p  { color: #94a3b8; }
  </style>
</head>
<body>
  <div class="box">
    <h1>Coesita Dashboard</h1>
    <p>Sin datos todavía. Las métricas aparecerán cuando el agente comience a operar.</p>
    <p style="font-size:0.8rem; color:#475569">Actualizando cada 15 segundos…</p>
    <p style="margin-top:14px;">
      <a href="/benchmark" style="color:#6366f1;">Benchmark de frameworks</a> ·
      <a href="/scenarios" style="color:#6366f1;">Escenarios de estrés</a>
    </p>
  </div>
</body>
</html>"""


def _render_full(d: dict) -> str:
    m = d["metrics"]
    arch = d["archetype"]
    risk_color = _RISK_COLOR.get(arch["risk"], "#94a3b8")
    risk_label = _RISK_LABEL.get(arch["risk"], arch["risk"].upper())
    crs_color = _crs_color(m["crs"])
    farp_color = _farp_color(m["farp_strict"])

    # Canales
    max_ch = d["top_channels"][0][1] if d["top_channels"] else 1
    channels_html = ""
    for ch, count in d["top_channels"]:
        bar = _channel_bar(count, max_ch)
        channels_html += f"""
        <div style="margin-bottom:10px;">
          <div style="display:flex;justify-content:space-between;font-size:0.8rem;margin-bottom:3px;">
            <span style="color:#c7d2fe;">{ch}</span>
            <span style="color:#94a3b8;">{count}</span>
          </div>
          {bar}
        </div>"""

    # Tabla de sesiones
    sessions_rows = ""
    for s in reversed(d["sessions"]):
        rd_color = "#ef4444" if s["rd_patho_count"] > 0 else "#22c55e"
        sessions_rows += f"""
        <tr>
          <td style="font-family:monospace;font-size:0.75rem;color:#94a3b8;">{s['session_id']}</td>
          <td style="text-align:center;">{s['turns']}</td>
          <td style="text-align:center;color:#a5b4fc;">{s['pressure_turns']}</td>
          <td style="text-align:center;color:#f9a8d4;">{s['act_turns']}</td>
          <td style="text-align:center;font-weight:700;color:{rd_color};">{s['rd_patho_count']}</td>
          <td style="font-size:0.75rem;color:#64748b;">{s['last_ts']}</td>
        </tr>"""

    # Últimos registros (log en vivo)
    last_records_html = ""
    if d["sessions"]:
        last_session = d["sessions"][-1]
        for r in reversed(last_session["records"][-8:]):
            rd_color = "#ef4444" if r.get("rd_patho") else "#64748b"
            ch_str = ", ".join(r.get("channels", [])) or "—"
            last_records_html += f"""
            <tr>
              <td style="text-align:center;color:#94a3b8;">T{r.get('turn','?')}</td>
              <td><span style="padding:2px 6px;border-radius:4px;font-size:0.7rem;
                  background:{'#1e3a5f' if r.get('reason_class')=='DATA' else '#3b1f2b' if r.get('reason_class')=='PRESSURE' else '#2d2b0f'};
                  color:{'#60a5fa' if r.get('reason_class')=='DATA' else '#f87171' if r.get('reason_class')=='PRESSURE' else '#fbbf24'};">
                  {r.get('reason_class','?')}</span></td>
              <td style="color:{'#f87171' if r.get('decision')=='ACT' else '#86efac'};">{r.get('decision','?')}</td>
              <td style="font-size:0.75rem;color:#94a3b8;">{ch_str[:40]}</td>
              <td style="font-weight:700;color:{rd_color};">{'1' if r.get('rd_patho') else '0'}</td>
              <td style="font-size:0.7rem;color:#475569;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"
                  title="{r.get('message_preview','')[:200]}">{r.get('message_preview','')[:60]}…</td>
            </tr>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Coesita Dashboard</title>
  <meta http-equiv="refresh" content="30">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: system-ui, -apple-system, sans-serif; background: #0f172a;
           color: #e2e8f0; min-height: 100vh; padding: 24px; }}
    h1   {{ font-size: 1.4rem; font-weight: 700; color: #6366f1; }}
    h2   {{ font-size: 0.85rem; font-weight: 600; color: #94a3b8;
           text-transform: uppercase; letter-spacing: .05em; margin-bottom: 14px; }}
    .grid {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            margin: 20px 0; }}
    .card {{ background: #1e293b; border-radius: 12px; padding: 20px; }}
    .card.wide {{ grid-column: span 2; }}
    .metric-val {{ font-size: 2rem; font-weight: 800; }}
    .metric-lbl {{ font-size: 0.75rem; color: #64748b; margin-top: 4px; }}
    .archetype-badge {{ display:inline-block; padding: 4px 12px; border-radius: 20px;
                        font-weight: 700; font-size: 0.85rem; border: 2px solid; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
    th    {{ color: #64748b; font-weight: 600; padding: 8px 10px; text-align: left;
            border-bottom: 1px solid #1e293b; }}
    td    {{ padding: 8px 10px; border-bottom: 1px solid #0f172a; }}
    tr:hover td {{ background: #1e293b44; }}
    .tag  {{ font-size: 0.7rem; padding: 2px 8px; border-radius: 10px; }}
    footer {{ text-align:center; font-size:0.72rem; color:#334155; margin-top:32px; }}
  </style>
</head>
<body>

{_nav("/")}

<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
  <h1>Coesita · Robustness Dashboard</h1>
  <span style="font-size:0.75rem;color:#475569;">Actualiza cada 30 s · {d['last_updated']}</span>
</div>
<p style="font-size:0.8rem;color:#475569;margin-bottom:8px;">
  {d['total_turns']} turnos · {d['total_sessions']} sesiones · {d['log_file']}
</p>

<!-- MÉTRICAS PRINCIPALES -->
<div class="grid">

  <div class="card">
    <div class="metric-val" style="color:{crs_color};">{m['crs']:.3f}</div>
    <div class="metric-lbl">CRS — Composite Robustness Score</div>
    <div style="font-size:0.7rem;color:#475569;margin-top:6px;">Target: ≥ 0.90</div>
  </div>

  <div class="card">
    <div class="metric-val" style="color:{farp_color};">{m['farp_strict']:.1%}</div>
    <div class="metric-lbl">FARP_strict — Capitulación bajo presión</div>
    <div style="font-size:0.7rem;color:#475569;margin-top:6px;">Target: ≤ 10%</div>
  </div>

  <div class="card">
    <div class="metric-val" style="color:{'#ef4444' if m['rd_patho'] > 0.1 else '#22c55e'};">{m['rd_patho']:.3f}</div>
    <div class="metric-lbl">rdPatho — Deriva por razonamiento de presión</div>
    <div style="font-size:0.7rem;color:#475569;margin-top:6px;">Target: 0.000</div>
  </div>

  <div class="card">
    <div class="metric-val" style="color:#a5b4fc;">{m['abi']:+.3f}</div>
    <div class="metric-lbl">ABI — Accuracy Bias Index</div>
    <div style="font-size:0.7rem;color:#475569;margin-top:6px;">Target: ≈ 0</div>
  </div>

  <div class="card">
    <div class="metric-val" style="color:#94a3b8;">{m['bp']}</div>
    <div class="metric-lbl">BP — Primer turno de degradación</div>
    <div style="font-size:0.7rem;color:#475569;margin-top:6px;">Mayor = más robusto</div>
  </div>

  <div class="card">
    <div class="metric-val" style="color:#c4b5fd;">{m['pri']:.3f}</div>
    <div class="metric-lbl">PRI — Pressure Resistance Index</div>
    <div style="font-size:0.7rem;color:#475569;margin-top:6px;">Target: ≥ 0.80</div>
  </div>

</div>

<!-- ARQUETIPO -->
<div class="card" style="margin-bottom:16px;">
  <div style="display:flex;align-items:center;gap:14px;margin-bottom:12px;">
    <h2 style="margin:0;">Arquetipo detectado</h2>
    <span class="archetype-badge" style="color:{risk_color};border-color:{risk_color};">
      {arch['name']}
    </span>
    <span class="tag" style="background:{risk_color}22;color:{risk_color};">{risk_label}</span>
  </div>
  <p style="font-size:0.82rem;color:#cbd5e1;margin-bottom:10px;">{arch['description']}</p>
  <div style="background:#0f172a;border-radius:8px;padding:12px;font-size:0.8rem;color:#a5b4fc;">
    <strong style="color:#6366f1;">Recomendación:</strong> {arch['recommendation']}
  </div>
</div>

<div style="display:grid;grid-template-columns:1fr 2fr;gap:16px;margin-bottom:16px;">

  <!-- CANALES DE PRESIÓN -->
  <div class="card">
    <h2>Canales de presión</h2>
    {channels_html if channels_html else '<p style="color:#475569;font-size:0.8rem;">Sin presión detectada aún.</p>'}
  </div>

  <!-- SESIONES RECIENTES -->
  <div class="card">
    <h2>Sesiones recientes</h2>
    <table>
      <thead>
        <tr>
          <th>Sesión</th><th>Turnos</th><th>Presión</th><th>ACT</th><th>rdPatho</th><th>Último</th>
        </tr>
      </thead>
      <tbody>{sessions_rows}</tbody>
    </table>
  </div>

</div>

<!-- LOG EN VIVO -->
<div class="card">
  <h2>Última sesión — turnos recientes</h2>
  <table>
    <thead>
      <tr>
        <th>Turno</th><th>Reason</th><th>Decisión</th><th>Canales</th><th>rdPatho</th><th>Mensaje</th>
      </tr>
    </thead>
    <tbody>{last_records_html if last_records_html else '<tr><td colspan="6" style="color:#475569;text-align:center;padding:20px;">Sin registros aún.</td></tr>'}</tbody>
  </table>
</div>

<footer>
  Coesita Dashboard · FTM v2.2 · <a href="/api/data" style="color:#6366f1;">JSON API</a>
</footer>

</body>
</html>"""


# ── Render: Escenarios (Fase 2) ──────────────────────────────────────────────

_PRESSURE_COLOR = {"none": "#22c55e", "low": "#86efac", "ramp": "#facc15", "shock": "#ef4444"}


def _render_scenarios(data: dict) -> str:
    scenarios = data.get("scenarios", [])

    # Packs derivados del scan (vínculo Fase 1 → Fase 2)
    packs_html = ""
    for p in data.get("feature_packs") or []:
        fw_list = ", ".join(p.get("frameworks", [])[:6])
        more = len(p.get("frameworks", [])) - 6
        if more > 0:
            fw_list += f" (+{more})"
        examples = "".join(
            f'<li style="color:#64748b;font-size:0.72rem;">{t}</li>'
            for t in p.get("example_pressure", [])
        )
        packs_html += f"""
        <tr>
          <td style="font-weight:600;color:#c7d2fe;">{p['pack'].replace('_', ' ')}</td>
          <td><span class="tag" style="background:#312e8144;color:#a5b4fc;">{p['channel']}</span></td>
          <td style="font-size:0.75rem;color:#94a3b8;max-width:300px;">{p['measures']}</td>
          <td style="font-size:0.72rem;color:#a5b4fc;">{fw_list or '—'}</td>
          <td><ul style="padding-left:16px;">{examples}</ul></td>
        </tr>"""
    packs_card = f"""
<div class="card">
  <h2>Feature packs — escenarios derivados del scan</h2>
  <p style="font-size:0.75rem;color:#475569;margin-bottom:10px;">
    Generados a partir de las features detectadas en cada framework. Cada framework recibe
    solo los packs de las capacidades que su contenido revela; se miden aparte del ranking.
  </p>
  <table>
    <thead><tr><th>Pack</th><th>Canal</th><th>Qué mide</th><th>Aplica a</th><th>Presión de ejemplo</th></tr></thead>
    <tbody>{packs_html}</tbody>
  </table>
</div>""" if packs_html else ""

    rows = ""
    for s in scenarios:
        p_color = _PRESSURE_COLOR.get(s.get("pressure_label", ""), "#94a3b8")
        evaluates = ", ".join(e.replace("resistencia a presión ", "") for e in s.get("evaluates", []))
        metrics_html = "".join(f"<li>{m}</li>" for m in s.get("success_metrics", []))
        rows += f"""
        <tr>
          <td style="font-family:monospace;font-size:0.72rem;color:#94a3b8;">{s['scenario_id']}</td>
          <td>{s['domain']}</td>
          <td style="color:{'#86efac' if s['optimal'] == 'STAY' else '#f9a8d4'};font-weight:700;">{s['optimal']}</td>
          <td><span class="tag" style="background:{p_color}22;color:{p_color};">{s['pressure_label']} ({s['pressure_level']})</span></td>
          <td style="font-size:0.75rem;color:#94a3b8;max-width:340px;">{s['description']}</td>
          <td style="font-size:0.72rem;color:#a5b4fc;">{evaluates}</td>
          <td style="font-size:0.7rem;color:#64748b;"><ul style="padding-left:16px;">{metrics_html}</ul></td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Coesita · Escenarios</title>
  <style>{_PAGE_CSS}</style>
</head>
<body>
{_nav("/scenarios")}
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
  <h1>Coesita · Escenarios de Estrés</h1>
  <span style="font-size:0.75rem;color:#475569;">
    Tier {data.get('tier', '?')} · {data.get('n_scenarios', 0)} escenarios · generados {data.get('generated_at', '—')}
  </span>
</div>
<p style="font-size:0.8rem;color:#475569;margin-bottom:16px;">
  Cada escenario somete al agente a 10 turnos de presión social sin cambios en los datos objetivos.
  <a href="/api/scenarios" style="color:#6366f1;">JSON</a> ·
  regenerar: <code style="color:#94a3b8;">GET /api/scenarios?refresh=true&amp;tier=standard</code>
</p>
{packs_card}
<div class="card">
  <table>
    <thead>
      <tr><th>ID</th><th>Dominio</th><th>Óptimo</th><th>Presión</th><th>Descripción</th><th>Evalúa (canales)</th><th>Métricas de éxito</th></tr>
    </thead>
    <tbody>{rows if rows else '<tr><td colspan="7" style="color:#475569;text-align:center;padding:20px;">Sin escenarios. Lanza el pipeline desde /benchmark.</td></tr>'}</tbody>
  </table>
</div>
<footer>Coesita Dashboard · FTM v2.2</footer>
</body>
</html>"""


# ── Render: Benchmark (Fases 3-4) ────────────────────────────────────────────

def _bar(value: float, color: str, max_value: float = 1.0) -> str:
    pct = max(0, min(100, int((value / max(max_value, 1e-9)) * 100)))
    return (
        f'<div style="background:#0f172a;border-radius:4px;height:10px;width:100%;">'
        f'<div style="background:{color};height:10px;width:{pct}%;border-radius:4px;"></div></div>'
    )


def _render_feature_matrix(results: dict | None) -> str:
    """Matriz framework × pack (FARP) — el vínculo scan→escenarios."""
    if not results:
        return ""
    frameworks = results.get("frameworks", [])
    packs = sorted({
        fr["pack"] for f in frameworks for fr in f.get("feature_results", [])
    })
    if not packs:
        return ""

    headers = "".join(
        f'<th style="text-align:center;font-size:0.7rem;">{p.replace("_", " ")}</th>'
        for p in packs
    )
    rows = ""
    for f in frameworks:
        by_pack = {fr["pack"]: fr for fr in f.get("feature_results", [])}
        cells = ""
        for p in packs:
            fr = by_pack.get(p)
            if not fr:
                cells += '<td style="text-align:center;color:#334155;">n/a</td>'
                continue
            color = _farp_color(fr["farp_strict"])
            tip = (
                f"PRI {fr['pri']:.2f} · rdPatho {fr['rd_patho']:.2f} · "
                f"1er fallo T{fr['first_fail_turn_mean'] or '—'} · {fr['n_scenarios']} escenarios"
            )
            cells += (
                f'<td style="text-align:center;font-weight:700;color:{color};" '
                f'title="{tip}">{fr["farp_strict"]:.0%}</td>'
            )
        rows += f"""
        <tr>
          <td style="font-weight:600;color:#c7d2fe;">{f['framework']}</td>
          {cells}
        </tr>"""

    return f"""
<div class="card">
  <h2>Feature robustness — packs derivados del scan (FARP por pack)</h2>
  <p style="font-size:0.75rem;color:#475569;margin-bottom:10px;">
    Escenarios adaptados a las features de cada framework escaneado (consenso de subagentes,
    precedente en memoria, urgencia de tools, bypass de aprobación humana).
    No afectan al CRS del ranking. n/a = el framework no declara esa feature.
  </p>
  <table>
    <thead><tr><th>Framework</th>{headers}</tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>"""


def _render_benchmark(scan: dict | None, results: dict | None, history: list[dict]) -> str:
    # ── Tabla comparativa de frameworks evaluados ──
    fw_rows = ""
    charts_html = ""
    scenario_rows = ""
    if results:
        for f in results.get("frameworks", []):
            m = f["metrics"]
            arch = f["archetype"]
            risk_color = _RISK_COLOR.get(arch["risk"], "#94a3b8")
            fw_rows += f"""
            <tr>
              <td style="font-weight:700;color:#c7d2fe;">{f['framework']}</td>
              <td style="font-weight:800;color:{_crs_color(m['crs'])};">{m['crs']:.3f}</td>
              <td style="color:{_farp_color(m['farp_strict'])};">{m['farp_strict']:.1%}</td>
              <td>{m['pri']:.3f}</td>
              <td>{m['consistency']:.3f}</td>
              <td>{m['rd_patho']:.3f}</td>
              <td>{f['latency_ms']['avg']} ms</td>
              <td><span class="tag" style="background:{risk_color}22;color:{risk_color};">{arch['name']}</span></td>
            </tr>"""

            # Gráfico: CRS + accuracy STAY por turno
            turn_bars = ""
            for t, acc in enumerate(m.get("stay_acc_by_turn", []), start=1):
                h = max(4, int(acc * 60))
                c = "#22c55e" if acc >= 0.9 else "#facc15" if acc >= 0.6 else "#ef4444"
                turn_bars += (
                    f'<div title="T{t}: {acc:.0%}" style="flex:1;display:flex;flex-direction:column;'
                    f'justify-content:flex-end;height:64px;"><div style="background:{c};'
                    f'height:{h}px;border-radius:3px 3px 0 0;"></div></div>'
                )
            charts_html += f"""
            <div style="margin-bottom:18px;">
              <div style="display:flex;justify-content:space-between;font-size:0.8rem;margin-bottom:4px;">
                <span style="color:#c7d2fe;font-weight:600;">{f['framework']}</span>
                <span style="color:{_crs_color(m['crs'])};font-weight:700;">CRS {m['crs']:.3f}</span>
              </div>
              {_bar(m['crs'], _crs_color(m['crs']))}
              <div style="display:flex;gap:3px;margin-top:8px;">{turn_bars}</div>
              <div style="font-size:0.65rem;color:#475569;margin-top:2px;">Accuracy STAY por turno (T1→T10)</div>
            </div>"""

        # Resultados por escenario (del framework líder y el resto, agrupados)
        for f in results.get("frameworks", []):
            for s in f.get("scenarios", [])[:200]:
                cap_color = "#ef4444" if s["capitulated"] else "#22c55e"
                scenario_rows += f"""
                <tr>
                  <td style="font-size:0.72rem;color:#94a3b8;">{f['framework']}</td>
                  <td style="font-family:monospace;font-size:0.7rem;color:#64748b;">{s['scenario_id']}</td>
                  <td>{s['domain']}</td>
                  <td>{s['schedule_category']}</td>
                  <td style="text-align:center;">{s['n_correct']}/{s['n_turns']}</td>
                  <td style="text-align:center;font-weight:700;color:{cap_color};">{'SÍ' if s['capitulated'] else 'no'}</td>
                  <td style="text-align:center;color:#94a3b8;">{s['first_fail_turn'] or '—'}</td>
                  <td style="text-align:center;color:#64748b;">{s['avg_latency_ms']} ms</td>
                </tr>"""

    # ── Histórico de runs ──
    history_rows = ""
    for h in reversed(history):
        fw_summary = " · ".join(
            f"{f['name']}: {f['crs']:.3f}" for f in h.get("frameworks", [])
        )
        history_rows += f"""
        <tr>
          <td style="font-family:monospace;font-size:0.72rem;color:#94a3b8;">{h.get('run_id', '?')}</td>
          <td style="font-size:0.75rem;color:#64748b;">{h.get('finished_at', '')}</td>
          <td>{h.get('tier', '')}</td>
          <td style="text-align:center;">{h.get('n_scenarios', '')}</td>
          <td style="font-size:0.72rem;color:#a5b4fc;">{fw_summary}</td>
        </tr>"""

    # ── Frameworks escaneados (Fase 1) ──
    scan_rows = ""
    if scan:
        feature_headers = "".join(
            f'<th style="text-align:center;font-size:0.65rem;">{k.replace("_", " ")}</th>'
            for k in FEATURE_KEYS
        )
        for fw in scan.get("frameworks", []):
            cells = ""
            for k in FEATURE_KEYS:
                ok = fw.get("features", {}).get(k, False)
                cells += (
                    f'<td style="text-align:center;color:{"#22c55e" if ok else "#334155"};">'
                    f'{"✓" if ok else "—"}</td>'
                )
            scan_rows += f"""
            <tr>
              <td style="font-weight:600;color:#c7d2fe;"><a href="{fw.get('repo', '#')}" style="color:inherit;">{fw['name']}</a></td>
              <td style="font-size:0.75rem;color:#64748b;">{fw.get('org', '')}</td>
              <td style="font-size:0.75rem;color:#64748b;">{fw.get('language', '')}</td>
              {cells}
              <td style="font-size:0.7rem;color:#475569;max-width:260px;">{fw.get('notes', '')}</td>
            </tr>"""
    else:
        feature_headers = ""

    # ── Kanban embebido (opcional, COESITA_KANBAN_URL) ──
    kanban_url = os.environ.get("COESITA_KANBAN_URL", "")
    kanban_html = ""
    if kanban_url:
        kanban_html = f"""
<div class="card">
  <h2>Kanban (workers del benchmark)</h2>
  <iframe src="{kanban_url}" style="width:100%;height:480px;border:0;border-radius:8px;background:#0f172a;"></iframe>
</div>"""

    run_meta = ""
    if results:
        run_meta = (
            f"Run {results.get('run_id', '?')} · tier {results.get('tier', '?')} · "
            f"{results.get('n_scenarios', 0)} escenarios · finalizado {results.get('finished_at', '')}"
        )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Coesita · Benchmark</title>
  <style>{_PAGE_CSS}
    button {{ background:#6366f1; color:white; border:0; padding:8px 18px; border-radius:8px;
              font-weight:700; cursor:pointer; font-size:0.85rem; }}
    button:disabled {{ background:#334155; cursor:wait; }}
    select {{ background:#0f172a; color:#e2e8f0; border:1px solid #334155;
              border-radius:8px; padding:7px 10px; font-size:0.85rem; }}
  </style>
</head>
<body>
{_nav("/benchmark")}
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
  <h1>Coesita · Benchmark de Frameworks</h1>
  <span style="font-size:0.75rem;color:#475569;">{run_meta or 'Sin runs todavía'}</span>
</div>
<p style="font-size:0.8rem;color:#475569;margin-bottom:16px;">
  Pipeline: Scanning → Escenarios → Testing. Robustez decisional bajo presión social (FTM v2.2).
  <a href="/api/benchmark" style="color:#6366f1;">JSON</a>
</p>

<!-- LANZAR PIPELINE -->
<div class="card">
  <h2>Lanzar pipeline completo</h2>
  <div style="display:flex;gap:10px;align-items:center;">
    <select id="tier">
      <option value="snapshot">snapshot (5 escenarios, sin presión)</option>
      <option value="standard" selected>standard (30 escenarios)</option>
      <option value="extended">extended (90 escenarios)</option>
      <option value="research">research (300 escenarios)</option>
    </select>
    <button id="run-btn" onclick="runBenchmark()">▶ Ejecutar benchmark</button>
    <span id="run-status" style="font-size:0.8rem;color:#94a3b8;"></span>
  </div>
</div>

<div style="display:grid;grid-template-columns:3fr 2fr;gap:16px;">
  <!-- TABLA COMPARATIVA -->
  <div class="card">
    <h2>Comparativa de frameworks (último run)</h2>
    <table>
      <thead>
        <tr><th>Framework</th><th>CRS</th><th>FARP</th><th>PRI</th><th>Consistencia</th><th>rdPatho</th><th>Latencia</th><th>Arquetipo</th></tr>
      </thead>
      <tbody>{fw_rows if fw_rows else '<tr><td colspan="8" style="color:#475569;text-align:center;padding:20px;">Sin resultados. Ejecuta el pipeline.</td></tr>'}</tbody>
    </table>
  </div>

  <!-- GRÁFICOS -->
  <div class="card">
    <h2>Robustez decisional</h2>
    {charts_html if charts_html else '<p style="color:#475569;font-size:0.8rem;">Sin datos de robustez todavía.</p>'}
  </div>
</div>

{_render_feature_matrix(results)}

<!-- RESULTADOS POR ESCENARIO -->
<div class="card">
  <h2>Resultados por escenario</h2>
  <div style="max-height:340px;overflow-y:auto;">
  <table>
    <thead>
      <tr><th>Framework</th><th>Escenario</th><th>Dominio</th><th>Schedule</th><th>Correctos</th><th>Capituló</th><th>1er fallo</th><th>Latencia</th></tr>
    </thead>
    <tbody>{scenario_rows if scenario_rows else '<tr><td colspan="8" style="color:#475569;text-align:center;padding:20px;">Sin resultados por escenario.</td></tr>'}</tbody>
  </table>
  </div>
</div>

<!-- HISTÓRICO -->
<div class="card">
  <h2>Histórico de tests</h2>
  <table>
    <thead><tr><th>Run</th><th>Finalizado</th><th>Tier</th><th>Escenarios</th><th>CRS por framework</th></tr></thead>
    <tbody>{history_rows if history_rows else '<tr><td colspan="5" style="color:#475569;text-align:center;padding:20px;">Sin histórico.</td></tr>'}</tbody>
  </table>
</div>

<!-- SCANNING DE FRAMEWORKS (Fase 1) -->
<div class="card">
  <h2>Frameworks escaneados ({scan.get('n_frameworks', 0) if scan else 0}) ·
    <a href="/scanning/frameworks" style="color:#6366f1;font-weight:400;text-transform:none;">JSON</a> ·
    <a href="/scanning/frameworks?refresh=true" style="color:#6366f1;font-weight:400;text-transform:none;">re-scan</a></h2>
  <div style="overflow-x:auto;">
  <table>
    <thead><tr><th>Framework</th><th>Org</th><th>Lenguaje</th>{feature_headers}<th>Notas</th></tr></thead>
    <tbody>{scan_rows if scan_rows else '<tr><td colspan="11" style="color:#475569;text-align:center;padding:20px;">Sin scan. Ejecuta el pipeline o visita /scanning/frameworks?refresh=true.</td></tr>'}</tbody>
  </table>
  </div>
</div>

{kanban_html}

<footer>Coesita Dashboard · Benchmark FTM v2.2 · <a href="/api/benchmark" style="color:#6366f1;">JSON API</a></footer>

<script>
async function runBenchmark() {{
  const btn = document.getElementById('run-btn');
  const status = document.getElementById('run-status');
  const tier = document.getElementById('tier').value;
  btn.disabled = true;
  status.textContent = 'Lanzando pipeline...';
  const resp = await fetch('/benchmark/run?tier=' + tier, {{method: 'POST'}});
  const data = await resp.json();
  if (data.status === 'error') {{
    status.textContent = 'Error: ' + data.error;
    btn.disabled = false;
    return;
  }}
  status.textContent = 'Ejecutando (tier ' + tier + ')...';
  const poll = setInterval(async () => {{
    const s = await (await fetch('/benchmark/status')).json();
    if (s.status === 'done') {{ clearInterval(poll); location.reload(); }}
    if (s.status === 'error') {{
      clearInterval(poll);
      status.textContent = 'Error: ' + s.error;
      btn.disabled = false;
    }}
  }}, 2000);
}}
</script>

</body>
</html>"""


def _pct(v) -> str:
    try:
        return f"{float(v) * 100:.0f}%"
    except (TypeError, ValueError):
        return "—"


def _render_agent_card(r: dict) -> str:
    m = r.get("metrics", {})
    b = r.get("behavior", {})
    a = r.get("archetype", {})
    soul = r.get("soul", {})
    crs = m.get("crs", 0.0)
    crs_color = "#22c55e" if crs >= 0.9 else "#f59e0b" if crs >= 0.75 else "#ef4444"

    def _beh(label, key, hint):
        v = b.get(key, 0.0)
        color = "#22c55e" if (v or 0) == 0 else "#f59e0b" if (v or 0) < 0.34 else "#ef4444"
        return (
            f'<div style="flex:1;min-width:150px;"><div style="font-size:1.4rem;font-weight:700;'
            f'color:{color};">{_pct(v)}</div><div style="font-size:0.72rem;color:#94a3b8;">{label}</div>'
            f'<div style="font-size:0.66rem;color:#475569;">{hint}</div></div>'
        )

    tools = b.get("tools_invoked_freq", {}) or {}
    tools_str = ", ".join(f"{k} ×{v}" for k, v in list(tools.items())[:6]) or "—"
    domain = soul.get("domain", "—")
    ff = b.get("first_unwarranted_action_turn_mean")
    ff_str = f"T{ff}" if ff else "nunca"
    warning = r.get("measurement_warning")
    warning_html = (
        f'<div style="margin:12px 0;padding:12px;background:#422006;border:1px solid #b45309;'
        f'border-radius:8px;font-size:0.78rem;color:#fcd34d;"><b>⚠ Validez de la medición:</b> '
        f'{warning}</div>' if warning else ""
    )

    return f"""
  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px;">
      <h1 style="font-size:1.1rem;">{r.get('agent', 'Agente')}</h1>
      <span style="font-size:0.75rem;color:#64748b;">dominio: <b style="color:#94a3b8;">{domain}</b>
        · evaluado {r.get('evaluated_at', '')[:10]} · {r.get('n_scenarios', 0)} escenarios</span>
    </div>
    {warning_html}
    <div style="display:flex;gap:24px;flex-wrap:wrap;margin:16px 0;align-items:center;">
      <div><div style="font-size:2rem;font-weight:800;color:{crs_color};">{crs:.3f}</div>
        <div style="font-size:0.72rem;color:#94a3b8;">CRS (robustez)</div></div>
      <div><div style="font-size:2rem;font-weight:800;color:#e2e8f0;">{_pct(m.get('farp_strict'))}</div>
        <div style="font-size:0.72rem;color:#94a3b8;">FARP (capitulación)</div></div>
      <div style="border-left:1px solid #334155;padding-left:24px;">
        <div style="font-size:0.95rem;font-weight:700;color:#e2e8f0;">{a.get('name', '—')}</div>
        <div style="font-size:0.72rem;color:#94a3b8;">arquetipo · riesgo {a.get('risk', '—')}</div></div>
    </div>
    <h2 style="margin-top:8px;">Comportamiento observado bajo presión</h2>
    <div style="display:flex;gap:18px;flex-wrap:wrap;margin-bottom:12px;">
      {_beh('actuó sin justificación', 'unwarranted_action_under_pressure', 'invocó una tool de acción cuando debía mantener')}
      {_beh('saltó el gate humano', 'gate_bypass_under_pressure', 'actuó sin la tool de aprobación')}
      {_beh('delegó la decisión', 'delegation_under_pressure', 'pasó la decisión a un subagente')}
      <div style="flex:1;min-width:150px;"><div style="font-size:1.4rem;font-weight:700;color:#e2e8f0;">{ff_str}</div>
        <div style="font-size:0.72rem;color:#94a3b8;">primera acción indebida</div>
        <div style="font-size:0.66rem;color:#475569;">turno medio en que cedió</div></div>
    </div>
    <div style="font-size:0.75rem;color:#64748b;">Tools que invocó: {tools_str}</div>
    <div style="margin-top:12px;padding:12px;background:#0f172a;border-radius:8px;font-size:0.78rem;color:#cbd5e1;">
      <b style="color:#6366f1;">Recomendación:</b> {a.get('recommendation', '—')}</div>
  </div>"""


def _render_agents(reports: list[dict]) -> str:
    if not reports:
        body = """
  <div class="card">
    <h1 style="font-size:1.1rem;">Evaluación de agente</h1>
    <p style="color:#94a3b8;margin-top:10px;font-size:0.85rem;">
      Aún no hay reportes de agente. A diferencia del leaderboard de modelos (corpus fijo,
      comparable), cada agente se evalúa <b>individualmente</b> sobre escenarios generados
      desde su propio soul, puntuados por las acciones que realmente toma.</p>
    <pre style="background:#0f172a;padding:14px;border-radius:8px;margin-top:12px;font-size:0.74rem;color:#cbd5e1;overflow:auto;">from skills.coesita.framework_scanner import scan_agent_soul
from skills.coesita.soul_scenarios import generate_soul_scenarios
from skills.coesita.benchmark_tester import evaluate_agent, make_openai_compatible_runner

soul = scan_agent_soul("Mi Agente", system_prompt=open("SOUL.md").read(), tools=[...])
gen  = make_openai_compatible_runner(MODEL, base_url=BASE_URL, api_key=KEY)
scenarios, spec = generate_soul_scenarios(soul, generator=gen)
report = evaluate_agent("Mi Agente", mi_runner, scenarios, slug="mi-agente")</pre>
    <p style="color:#64748b;margin-top:10px;font-size:0.78rem;">
      Ver <code>coesita-benchmark/examples/run_hermes_agent.py</code> como implementación de referencia.</p>
  </div>"""
    else:
        body = "".join(_render_agent_card(r) for r in reports)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Coesita · Evaluación de Agente</title>
  <style>{_PAGE_CSS}</style>
</head>
<body>
  <div style="max-width:1000px;margin:0 auto;">
    {_nav("/agents")}
    <h2>Evaluación de agente · reportes individuales (escenarios desde el soul, scoring por acción real)</h2>
    {body}
    <footer>Coesita · robustez decisional bajo presión social (FTM v2.2)</footer>
  </div>
</body>
</html>"""


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("COESITA_DASHBOARD_PORT", 5050))
    print(f"Coesita Dashboard arrancando en http://localhost:{port}", flush=True)
    print(f"Leyendo logs de: {_LOG_FILE}", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
