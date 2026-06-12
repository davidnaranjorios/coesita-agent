"""
Coesita Dashboard — FTM v2.2
==============================
Local web server: live agent-robustness metrics (decisions.jsonl) plus the
framework benchmark pipeline (Scanning → Scenarios → Testing).

Routes:
    /                     live robustness metrics (FTM v10)
    /benchmark            framework comparison + launch pipeline
    /scenarios            generated stress scenarios
    /scanning/frameworks  framework scan (JSON, ?refresh=true)
    POST /benchmark/run   launches the full pipeline in the background
    /benchmark/status     pipeline status
    /api/data /api/scenarios /api/benchmark   JSON for integrations

Start:
    coesita dashboard            # or: python -m coesita.dashboard

Open in a browser:
    http://localhost:5050
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from coesita.benchmark_store import data_dir


def _log_file():
    return data_dir() / "decisions.jsonl"


# ── FTM engine ────────────────────────────────────────────────────────────────
from coesita.ftm_engine import (
    TIER_META, TurnResult, compute_metrics, detect_archetype,
)

# ── Pipeline de benchmark (Fases 1-4) ─────────────────────────────────────────
import threading

from coesita.benchmark_store import load_history
from coesita.benchmark_tester import load_results, run_full_pipeline
from coesita.framework_scanner import FEATURE_KEYS, load_scan, run_scan
from coesita.scenario_generator import load_scenarios, run_generation

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Coesita Dashboard", docs_url=None, redoc_url=None)


# ── Lectura y conversión del log ──────────────────────────────────────────────

def _load_records() -> list[dict]:
    if not _log_file().exists():
        return []
    records = []
    with open(_log_file(), encoding="utf-8") as f:
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
        "log_file": str(_log_file()),
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
    "minimal": "OPTIMAL",
    "low": "GOOD",
    "medium": "MODERATE",
    "high": "HIGH",
    "critical": "CRITICAL",
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
        return {"status": "error", "error": f"invalid tier: {tier!r}", "valid_tiers": sorted(TIER_META)}
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


# ── Render HTML ───────────────────────────────────────────────────────────────

_NAV_LINKS = [
    ("/", "Robustness"),
    ("/benchmark", "Benchmark"),
    ("/scenarios", "Scenarios"),
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
    <p>No data yet. Metrics will appear once your agent starts logging decisions.</p>
    <p style="font-size:0.8rem; color:#475569">Refreshing every 15 seconds…</p>
    <p style="margin-top:14px;">
      <a href="/benchmark" style="color:#6366f1;">Framework benchmark</a> ·
      <a href="/scenarios" style="color:#6366f1;">Stress scenarios</a>
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
  <span style="font-size:0.75rem;color:#475569;">Refreshes every 30 s · {d['last_updated']}</span>
</div>
<p style="font-size:0.8rem;color:#475569;margin-bottom:8px;">
  {d['total_turns']} turns · {d['total_sessions']} sessions · {d['log_file']}
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
    <div class="metric-lbl">FARP_strict — Capitulation under pressure</div>
    <div style="font-size:0.7rem;color:#475569;margin-top:6px;">Target: ≤ 10%</div>
  </div>

  <div class="card">
    <div class="metric-val" style="color:{'#ef4444' if m['rd_patho'] > 0.1 else '#22c55e'};">{m['rd_patho']:.3f}</div>
    <div class="metric-lbl">rdPatho — Pressure-reasoning drift</div>
    <div style="font-size:0.7rem;color:#475569;margin-top:6px;">Target: 0.000</div>
  </div>

  <div class="card">
    <div class="metric-val" style="color:#a5b4fc;">{m['abi']:+.3f}</div>
    <div class="metric-lbl">ABI — Accuracy Bias Index</div>
    <div style="font-size:0.7rem;color:#475569;margin-top:6px;">Target: ≈ 0</div>
  </div>

  <div class="card">
    <div class="metric-val" style="color:#94a3b8;">{m['bp']}</div>
    <div class="metric-lbl">BP — First degradation turn</div>
    <div style="font-size:0.7rem;color:#475569;margin-top:6px;">Higher = more robust</div>
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
    <h2 style="margin:0;">Detected archetype</h2>
    <span class="archetype-badge" style="color:{risk_color};border-color:{risk_color};">
      {arch['name']}
    </span>
    <span class="tag" style="background:{risk_color}22;color:{risk_color};">{risk_label}</span>
  </div>
  <p style="font-size:0.82rem;color:#cbd5e1;margin-bottom:10px;">{arch['description']}</p>
  <div style="background:#0f172a;border-radius:8px;padding:12px;font-size:0.8rem;color:#a5b4fc;">
    <strong style="color:#6366f1;">Recommendation:</strong> {arch['recommendation']}
  </div>
</div>

<div style="display:grid;grid-template-columns:1fr 2fr;gap:16px;margin-bottom:16px;">

  <!-- CANALES DE PRESIÓN -->
  <div class="card">
    <h2>Pressure channels</h2>
    {channels_html if channels_html else '<p style="color:#475569;font-size:0.8rem;">No pressure detected yet.</p>'}
  </div>

  <!-- SESIONES RECIENTES -->
  <div class="card">
    <h2>Recent sessions</h2>
    <table>
      <thead>
        <tr>
          <th>Session</th><th>Turns</th><th>Pressure</th><th>ACT</th><th>rdPatho</th><th>Last</th>
        </tr>
      </thead>
      <tbody>{sessions_rows}</tbody>
    </table>
  </div>

</div>

<!-- LOG EN VIVO -->
<div class="card">
  <h2>Latest session — recent turns</h2>
  <table>
    <thead>
      <tr>
        <th>Turn</th><th>Reason</th><th>Decision</th><th>Channels</th><th>rdPatho</th><th>Message</th>
      </tr>
    </thead>
    <tbody>{last_records_html if last_records_html else '<tr><td colspan="6" style="color:#475569;text-align:center;padding:20px;">No records yet.</td></tr>'}</tbody>
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

    # Scan-driven packs (Phase 1 → Phase 2 link)
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
  <h2>Feature packs — scenarios derived from the scan</h2>
  <p style="font-size:0.75rem;color:#475569;margin-bottom:10px;">
    Generated from the feature matrix in frameworks.json. Each framework only receives
    the packs for the capabilities it declares; measured separately from the ranking.
  </p>
  <table>
    <thead><tr><th>Pack</th><th>Channel</th><th>What it measures</th><th>Applies to</th><th>Example pressure</th></tr></thead>
    <tbody>{packs_html}</tbody>
  </table>
</div>""" if packs_html else ""

    rows = ""
    for s in scenarios:
        p_color = _PRESSURE_COLOR.get(s.get("pressure_label", ""), "#94a3b8")
        evaluates = ", ".join(e.replace("resistance to ", "").replace(" pressure", "") for e in s.get("evaluates", []))
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
  <title>Coesita · Scenarios</title>
  <style>{_PAGE_CSS}</style>
</head>
<body>
{_nav("/scenarios")}
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
  <h1>Coesita · Stress Scenarios</h1>
  <span style="font-size:0.75rem;color:#475569;">
    Tier {data.get('tier', '?')} · {data.get('n_scenarios', 0)} scenarios · generated {data.get('generated_at', '—')}
  </span>
</div>
<p style="font-size:0.8rem;color:#475569;margin-bottom:16px;">
  Each scenario subjects the agent to 10 turns of social pressure while the objective data never changes.
  <a href="/api/scenarios" style="color:#6366f1;">JSON</a> ·
  regenerate: <code style="color:#94a3b8;">GET /api/scenarios?refresh=true&amp;tier=standard</code>
</p>
{packs_card}
<div class="card">
  <table>
    <thead>
      <tr><th>ID</th><th>Domain</th><th>Optimal</th><th>Pressure</th><th>Description</th><th>Evaluates (channels)</th><th>Success metrics</th></tr>
    </thead>
    <tbody>{rows if rows else '<tr><td colspan="7" style="color:#475569;text-align:center;padding:20px;">No scenarios yet. Launch the pipeline from /benchmark.</td></tr>'}</tbody>
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
    """Framework × pack matrix (FARP) — the scan→scenarios link."""
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
                f"first fail T{fr['first_fail_turn_mean'] or '—'} · {fr['n_scenarios']} scenarios"
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
  <h2>Feature robustness — scan-driven packs (FARP per pack)</h2>
  <p style="font-size:0.75rem;color:#475569;margin-bottom:10px;">
    Scenarios tailored to each scanned framework's features (subagent consensus,
    memory precedent, tool urgency, human-gate bypass). They do not affect the
    headline CRS ranking. n/a = the framework does not declare that feature.
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
              <div style="font-size:0.65rem;color:#475569;margin-top:2px;">STAY accuracy per turn (T1→T10)</div>
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
                  <td style="text-align:center;font-weight:700;color:{cap_color};">{'YES' if s['capitulated'] else 'no'}</td>
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
  <h2>Kanban (benchmark workers)</h2>
  <iframe src="{kanban_url}" style="width:100%;height:480px;border:0;border-radius:8px;background:#0f172a;"></iframe>
</div>"""

    run_meta = ""
    if results:
        run_meta = (
            f"Run {results.get('run_id', '?')} · tier {results.get('tier', '?')} · "
            f"{results.get('n_scenarios', 0)} scenarios · finished {results.get('finished_at', '')}"
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
  <h1>Coesita · Framework Benchmark</h1>
  <span style="font-size:0.75rem;color:#475569;">{run_meta or 'No runs yet'}</span>
</div>
<p style="font-size:0.8rem;color:#475569;margin-bottom:16px;">
  Pipeline: Scanning → Scenarios → Testing. Decisional robustness under social pressure (FTM v2.2).
  <a href="/api/benchmark" style="color:#6366f1;">JSON</a>
</p>

<!-- LANZAR PIPELINE -->
<div class="card">
  <h2>Launch full pipeline</h2>
  <div style="display:flex;gap:10px;align-items:center;">
    <select id="tier">
      <option value="snapshot">snapshot (5 scenarios, no pressure)</option>
      <option value="standard" selected>standard (30 scenarios)</option>
      <option value="extended">extended (90 scenarios)</option>
      <option value="research">research (300 scenarios)</option>
    </select>
    <button id="run-btn" onclick="runBenchmark()">▶ Run benchmark</button>
    <span id="run-status" style="font-size:0.8rem;color:#94a3b8;"></span>
  </div>
</div>

<div style="display:grid;grid-template-columns:3fr 2fr;gap:16px;">
  <!-- TABLA COMPARATIVA -->
  <div class="card">
    <h2>Framework comparison (latest run)</h2>
    <table>
      <thead>
        <tr><th>Framework</th><th>CRS</th><th>FARP</th><th>PRI</th><th>Consistency</th><th>rdPatho</th><th>Latency</th><th>Archetype</th></tr>
      </thead>
      <tbody>{fw_rows if fw_rows else '<tr><td colspan="8" style="color:#475569;text-align:center;padding:20px;">No results yet. Run the pipeline.</td></tr>'}</tbody>
    </table>
  </div>

  <!-- GRÁFICOS -->
  <div class="card">
    <h2>Decisional robustness</h2>
    {charts_html if charts_html else '<p style="color:#475569;font-size:0.8rem;">No robustness data yet.</p>'}
  </div>
</div>

{_render_feature_matrix(results)}

<!-- RESULTADOS POR ESCENARIO -->
<div class="card">
  <h2>Results per scenario</h2>
  <div style="max-height:340px;overflow-y:auto;">
  <table>
    <thead>
      <tr><th>Framework</th><th>Scenario</th><th>Domain</th><th>Schedule</th><th>Correct</th><th>Capitulated</th><th>First fail</th><th>Latency</th></tr>
    </thead>
    <tbody>{scenario_rows if scenario_rows else '<tr><td colspan="8" style="color:#475569;text-align:center;padding:20px;">No per-scenario results yet.</td></tr>'}</tbody>
  </table>
  </div>
</div>

<!-- HISTÓRICO -->
<div class="card">
  <h2>Test history</h2>
  <table>
    <thead><tr><th>Run</th><th>Finished</th><th>Tier</th><th>Scenarios</th><th>CRS per framework</th></tr></thead>
    <tbody>{history_rows if history_rows else '<tr><td colspan="5" style="color:#475569;text-align:center;padding:20px;">No history yet.</td></tr>'}</tbody>
  </table>
</div>

<!-- SCANNING DE FRAMEWORKS (Fase 1) -->
<div class="card">
  <h2>Scanned frameworks ({scan.get('n_frameworks', 0) if scan else 0}) ·
    <a href="/scanning/frameworks" style="color:#6366f1;font-weight:400;text-transform:none;">JSON</a> ·
    <a href="/scanning/frameworks?refresh=true" style="color:#6366f1;font-weight:400;text-transform:none;">re-scan</a></h2>
  <div style="overflow-x:auto;">
  <table>
    <thead><tr><th>Framework</th><th>Org</th><th>Language</th>{feature_headers}<th>Notes</th></tr></thead>
    <tbody>{scan_rows if scan_rows else '<tr><td colspan="11" style="color:#475569;text-align:center;padding:20px;">No scan yet. Run the pipeline or visit /scanning/frameworks?refresh=true.</td></tr>'}</tbody>
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
  status.textContent = 'Launching pipeline...';
  const resp = await fetch('/benchmark/run?tier=' + tier, {{method: 'POST'}});
  const data = await resp.json();
  if (data.status === 'error') {{
    status.textContent = 'Error: ' + data.error;
    btn.disabled = false;
    return;
  }}
  status.textContent = 'Running (tier ' + tier + ')...';
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


# ── Entry point ───────────────────────────────────────────────────────────────

def main(port: int | None = None, host: str = "0.0.0.0") -> None:
    """Start the Coesita dashboard server (used by the `coesita dashboard` CLI)."""
    port = port or int(os.environ.get("COESITA_DASHBOARD_PORT", 5050))
    print(f"Coesita Dashboard starting at http://localhost:{port}", flush=True)
    print(f"Data directory: {data_dir()}", flush=True)
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
