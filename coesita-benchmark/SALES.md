# Coesita Benchmark — Commercial One-Pager

## The problem it solves

Most AI agent evaluations test *capability*: can the model do the task?
Production incidents hinge on something harder to measure: does the agent
**keep doing the right thing** when humans push back — emotionally, urgently,
hierarchically — while the objective data stays exactly the same?

In published research across 8 frontier models, the average model capitulated
to social pressure in **28.7% of hold-the-line scenarios**. The worst performer
caved in **54.7%** of cases.

Coesita measures this. Then it tells you *why* it happens and how to fix it.

---

## What the buyer gets

### 1. A complete evaluation pipeline — one command

```bash
docker compose up -d          # → http://localhost:5050/benchmark
# click ▶ Run benchmark
```

The pipeline scans frameworks, generates 30–300 stress scenarios, tests each
runner in parallel, and renders a comparison dashboard — all offline, no API
keys required to see it work.

### 2. Research-grade metrics

| Metric | What it measures |
|---|---|
| **CRS** (Composite Robustness Score) | Overall score 0–1. Target ≥ 0.90. |
| **FARP** (False Action Rate under Pressure) | % of scenarios where the agent caved. |
| **PRI** (Pressure Resistance Index) | Stability across pressure intensity levels. |
| **rdPatho** (Reasoning Drift Pathology) | % of decisions reasoned with social pressure instead of data. |
| **Failure archetype** | Which of 7 patterns the agent exhibits, with the validated prompt fix. |

### 3. Content-driven framework scanning + feature packs

Point the scanner at a framework's actual artifacts (system prompt, RAG corpus,
code) — it detects capabilities from the content, no manual tagging. Detected
capabilities trigger targeted stress packs:

| Capability | Stress pack | What it tests |
|---|---|---|
| Subagents / multi-agent | *Delegated authority* | "3 of your 4 workers recommend escalating" |
| Persistent memory | *Precedent exploitation* | "Last time you faced this you escalated" |
| Tool use | *Tool urgency* | "Just run rollback() to reassure everyone" |
| Human-in-the-loop | *Gate bypass* | "The approver is offline — proceed now" |

Feature results are reported separately so they don't distort the headline ranking.

### 4. Proven interventions

The included **Data Anchoring block** reduced capitulation from 54.7% → 18.7%
(p < 0.0001) on the worst-performing frontier model. Every failure archetype
ships with its validated prompt intervention.

### 5. Agent instrumentation SDK

Drop two lines into any agent to log live decisions and get a session robustness
report — FARP, CRS, archetype — on the same dashboard:

```python
from coesita import DecisionLogger, evaluate_session
logger = DecisionLogger(session_id="prod-42")
# on each turn: logger.log_decision(...)
report = evaluate_session("prod-42")
```

### 6. Zero-dependency core

Pure Python stdlib engine. Only FastAPI + Uvicorn for the dashboard.
Runs on Python ≥ 3.10, bare metal or Docker.

---

## Who it's for

| Buyer | Use case |
|---|---|
| **AI teams shipping agents** | Pre-release gate: CRS ≥ 0.90 before deploy. |
| **Framework vendors** | Differentiate with a published robustness score. |
| **Enterprise risk / compliance** | Demonstrate that AI decisions don't drift under pressure. |
| **AI safety researchers** | Extend the FTM v2.2 corpus; publish reproducible results. |

---

## Pricing tiers (example — adjust before launch)

| Tier | Price | Seats | Source access | Support |
|---|---|---|---|---|
| **Indie** | $299 one-time | 1 dev | Wheel + Docker image | Community |
| **Team** | $999 one-time | Up to 10 | Full source | Email, 5 business days |
| **Enterprise** | Contact us | Unlimited | Full source + audit trail | Priority SLA |

All tiers: commercial use allowed, no royalties, no per-run fees.

---

## FAQ

**Does it require internet / API keys?**
No. The built-in baselines run offline in under a second. Add your own
OpenAI-compatible endpoint to benchmark a real model.

**Can I benchmark my LangGraph / CrewAI / AutoGen app?**
Yes. Export `COESITA_BENCHMARK_RUNNERS` pointing at your endpoint, run
`coesita run`. The scanner auto-detects which stress packs apply.

**Are the published research numbers reproducible?**
Yes. The FTM v2.2 engine is the exact port from the Servitorship Bias taxonomy
(D. Naranjo, 2026). Run tier `research` (300 scenarios) to reproduce the paper figures.

**Can I extend it with new domains or pressure channels?**
Yes. Add entries to `DOMAINS` / `PRESSURE_TEXTS` in `ftm_engine.py` and add tests.
The rest of the pipeline picks them up automatically.

---

## Delivery

Buyers receive:
- Python wheel (`coesita_benchmark-*.whl`) — install with `pip install`
- Docker image (`ghcr.io/<your-org>/coesita-benchmark:latest`) — pull and run
- Full source (private repo access via GitHub invitation for Team/Enterprise)
- `QUICKSTART.md` — up and running in 60 seconds

*For demo or purchase inquiries: [your contact here]*
