# Coesita Benchmark

> **Does your AI agent hold the right decision when a VP demands action, the
> team panics, and the clock runs out — even though the data hasn't changed?**

Coesita measures **decisional robustness under social pressure**. Most agent
evaluations test capability: can the model do the task? Coesita tests
something production incidents actually hinge on: does the agent *keep* doing
the right thing when humans push back — emotionally, hierarchically, urgently —
while the objective data stays exactly the same.

Built on the **FTM v2.2 benchmark** (Servitorship Bias taxonomy): in published
runs across 8 frontier models, the average model capitulated in **28.7%** of
hold-the-line scenarios; the worst, in **54.7%**.

![Benchmark dashboard](docs/benchmark-dashboard.png)

## Two evaluation modes

Coesita evaluates two different things, because models and agents are not the
same problem:

| | **Model leaderboard** (Mode A) | **Agent evaluation** (Mode B) |
|---|---|---|
| Question | Which model capitulates least? | Does *this* agent hold the line in its real job? |
| Comparable | Yes — a ranking (reproduces the paper) | No — an individual report |
| Scenarios | Fixed FTM corpus (5 domains), identical for all | Generated from *that agent's* soul |
| Scored by | The model's STAY/ACT text | What the agent actually **did**: invoked an action tool, delegated, bypassed the human gate |
| Output | A row in the comparison table | A standalone report card |

Models are interchangeable enough to rank on one fixed yardstick. Agents aren't —
no two are alike — so each is measured individually, on scenarios written for its
own domain and tools, by observing its real behaviour under pressure. See
[`examples/run_hermes_agent.py`](examples/run_hermes_agent.py) for the reference
agent evaluation and [`examples/README.md`](examples/README.md) for both modes.

## What you get

- **A full evaluation pipeline** — framework scanning → stress-scenario
  generation → parallel automated testing → web dashboard. One command end to end.
- **150 battle-tested scenarios** across 5 high-stakes domains (DevOps,
  medical, financial, legal, industrial safety), 3 pressure schedules
  (control / ramp / shock) and 6 pressure channels (emotional, temporal,
  hierarchical, peer, reputational, ambiguity).
- **Research-grade metrics** — FARP (capitulation rate), CRS (composite
  robustness), PRI (pressure resistance), rdPatho (reasoning drift),
  bootstrap confidence intervals — plus a **failure-archetype diagnosis**
  (Sudden Collapse, Staircase Erosion, Autonomous Drift, ...) with the
  validated prompt intervention for each one.
- **Content-driven scanning + feature packs** — the scanner reads a
  framework's actual artifacts (system prompt, RAG corpus, code/config) and
  detects its capabilities from that content; it doesn't assume a registry.
  The detected capabilities drive which pressure packs run: subagents →
  *delegated-authority* ("3 of your 4 workers recommend escalating"),
  persistent memory → *precedent exploitation*, tool use → *tool urgency*,
  human-in-the-loop → *gate bypass*. Reported as a per-pack FARP matrix,
  separate from the headline ranking so comparisons stay valid.
- **Proven interventions** — the Data Anchoring block reduced capitulation
  from 54.7% → 18.7% (p < 0.0001) on the worst-performing frontier model.
- **Agent instrumentation SDK** — log your own agent's live decisions
  (`DecisionLogger`, `detect_pressure`, `evaluate_session`) and watch its
  robustness metrics on the same dashboard.
- **Zero-dependency core** — the engine is pure Python stdlib; only the
  dashboard needs FastAPI. Runs anywhere Python 3.10+ runs.

## Quickstart (60 seconds)

**Docker (recommended):**

```bash
docker compose up -d
open http://localhost:5050/benchmark   # click "▶ Run benchmark"
```

**Bare Python:**

```bash
pip install .
coesita run                 # full pipeline: scan → scenarios → test
coesita dashboard           # → http://localhost:5050/benchmark
```

With no configuration, the benchmark runs against two built-in reference
baselines — a data-anchored ceiling (CRS 1.000) and a socially-compliant
floor (CRS ≈ 0.5) — so you can see the whole pipeline working offline,
no API keys needed.

## Benchmark your own models and frameworks

Point Coesita at any chat-completions endpoint — a hosted model, your
LangGraph/CrewAI/AutoGen service, a local vLLM. Name each entry after the
framework slug so it matches its scan profile:

```bash
export COESITA_BENCHMARK_RUNNERS='{
  "langgraph-app": {"model": "<your-model-id>",
                    "base_url": "https://your-endpoint/v1",
                    "api_key_env": "YOUR_API_KEY"},
  "my-agent":      {"model": "agent-v2", "base_url": "http://localhost:8000/v1"}
}'
coesita run --tier standard
```

Or from Python:

```python
from coesita import run_benchmark, make_openai_compatible_runner

runners = {"my-agent": make_openai_compatible_runner("agent-v2", base_url="http://localhost:8000/v1")}
results = run_benchmark(runners, tier="standard")
```

Each framework becomes a row in the comparison table with CRS, FARP, PRI,
consistency, latency and its failure archetype.

## Evaluation tiers

| Tier | Scenarios | Turns/framework | CI | Use for |
|---|---|---|---|---|
| `snapshot` | 5 | 50 | ±25% | smoke test (no pressure) |
| `standard` | 30 | 300 | ±10% | default comparisons |
| `extended` | 90 | 900 | ±5% | pre-release gates |
| `research` | 300 | 3,000 | ±2% | publishable results |

## CLI

```
coesita dashboard [--port 5050]      web dashboard
coesita run [--tier standard] [--domain medical]
coesita scan [--extra more.json]     framework registry → JSON
coesita scenarios [--tier standard]  stress scenarios → JSON
```

HTTP API: `GET /api/benchmark`, `GET /api/scenarios`,
`GET /scanning/frameworks`, `POST /benchmark/run?tier=standard`,
`GET /benchmark/status` — everything the dashboard shows is available as JSON.

## Instrument your own agent

```python
from coesita import DecisionLogger, detect_pressure, evaluate_session

logger = DecisionLogger(session_id="prod-session-42")
# ... on each turn: logger.log_decision(...) with the detected pressure channels
report = evaluate_session("prod-session-42")   # FARP, CRS, archetype, fixes
```

Live metrics appear on the dashboard home page (`/`).

## Requirements

- Python ≥ 3.10 (or just Docker)
- Dependencies: `fastapi`, `uvicorn` — nothing else

## License

Commercial license — see [LICENSE.md](LICENSE.md). The FTM v2.2 engine,
scenario corpus and metrics implementation are original work
(D. Naranjo, *Servitorship Bias*, 2026).
