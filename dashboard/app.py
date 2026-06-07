"""
Coesita Dashboard — FTM v2.2
==============================
Servidor web local que lee decisions.jsonl y muestra las métricas
de robustez del agente en tiempo real.

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
    TurnResult, compute_metrics, detect_archetype,
)

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


# ── Render HTML ───────────────────────────────────────────────────────────────

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


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("COESITA_DASHBOARD_PORT", 5050))
    print(f"Coesita Dashboard arrancando en http://localhost:{port}", flush=True)
    print(f"Leyendo logs de: {_LOG_FILE}", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
