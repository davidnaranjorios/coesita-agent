# Coesita Benchmark — Demo Guide

This guide walks through a complete demo in under 5 minutes.
No API key needed. Everything runs offline.

---

## Option A — Single command (recommended)

```bash
cd coesita-benchmark
pip install .
coesita demo
```

That's it. The CLI runs the full pipeline, prints a summary, then opens the
dashboard at `http://localhost:5050/benchmark`.

---

## Option B — Docker (zero Python setup)

```bash
cd coesita-benchmark
docker compose up -d
```

Wait ~10 seconds, then open `http://localhost:5050/benchmark` and click
**▶ Run benchmark**.

---

## What you'll see

### Terminal output (during `coesita demo` / `coesita run`)

```
=== Coesita Demo ===
Running benchmark pipeline (tier: standard)...

  Scenarios: 30  |  Frameworks scanned: 10
  Ceiling (data-anchored):  CRS 1.000  FARP  0%
  Floor  (social-compliant): CRS 0.515  FARP 67%

Pipeline done. Starting dashboard → http://localhost:5050/benchmark
Press Ctrl-C to stop.
```

The 30-scenario standard tier finishes in under a second with the built-in
baselines (no network calls).

### Dashboard — `/benchmark`

You'll see a comparison table with two rows:

| Framework | CRS ▼ | FARP | PRI | Archetype |
|---|---|---|---|---|
| baseline-data-anchored | **1.000** | **0%** | 1.000 | Pressure Resistant |
| baseline-social-compliant | 0.515 | 67% | 0.312 | Staircase Erosion |

Below the table: the **Feature robustness matrix** — a 2×4 grid showing each
baseline's FARP for the four capability-driven stress packs:
`delegated_authority`, `precedent_exploitation`, `tool_urgency`, `gate_bypass`.

The anchored baseline holds at 0% across all packs; the compliant baseline
collapses above 50% in each one.

### Dashboard — `/scenarios`

Lists all 30 generated scenarios (domain, optimal decision, schedule, pressure
channels) plus the four feature packs with example pressure messages.

---

## Benchmarking a real model

Add your OpenAI-compatible endpoint:

```bash
export COESITA_BENCHMARK_RUNNERS='{
  "my-agent": {
    "model": "your-model-id",
    "base_url": "https://your-endpoint/v1",
    "api_key_env": "YOUR_API_KEY"
  }
}'
coesita run --tier standard
```

Tier `standard` = 30 scenarios × 10 turns = 300 API calls per runner.
Expected cost: roughly $1–5 depending on model pricing.

The new row appears in the comparison table between the ceiling and the floor —
showing exactly where your agent sits on the robustness spectrum.

---

## Key numbers to look for

| Number | Healthy | Needs work |
|---|---|---|
| CRS | ≥ 0.90 | < 0.75 |
| FARP (strict) | ≤ 10% | > 25% |
| rdPatho | 0.000 | > 0.30 |
| PRI | ≥ 0.80 | < 0.50 |

If the archetype is **Staircase Erosion** or **Sudden Collapse**, the dashboard
shows the validated prompt intervention (Data Anchoring, Self-Check, etc.) that
reduces capitulation.

---

## Screenshot

![Benchmark dashboard](docs/benchmark-dashboard.png)

*(Captured from a local run. Your numbers will match the baselines exactly
since the built-in runners are deterministic.)*
