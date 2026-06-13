# Quickstart

## 1. Run it (pick one)

**Docker — zero setup:**

```bash
docker compose up -d
```

**Python:**

```bash
pip install .
coesita dashboard &
```

## 2. Open the dashboard

http://localhost:5050/benchmark — click **▶ Run benchmark** (tier `standard`).

It finishes in under a second against the built-in baselines and the page
reloads with:

- **Framework comparison** — the data-anchored baseline scores CRS 1.000 /
  FARP 0%; the socially-compliant baseline collapses to CRS ≈ 0.5 / FARP ≈ 67%.
  That spread is the instrument working.
- **Robustness charts** — STAY accuracy per turn; watch the compliant baseline
  turn red at T3, two turns after pressure starts.
- **Per-scenario results, run history, and the scanned framework registry.**

## 3. Benchmark something real

```bash
cp .env.example .env     # add your endpoint + API key, then:
docker compose up -d --force-recreate
```

or:

```bash
export COESITA_BENCHMARK_RUNNERS='{"my-agent": {"model": "<your-model-id>", "base_url": "https://your-endpoint/v1", "api_key_env": "YOUR_API_KEY"}}'
export YOUR_API_KEY=...
coesita run --tier standard
```

Heads-up on cost: `standard` = 300 LLM calls per framework (30 scenarios × 10
turns). Use `--domain devops_server` to cut it to 60 while iterating.

## 4. Read the diagnosis

Each framework gets a **failure archetype** with the validated countermeasure —
e.g. *Sudden Collapse* → add the Data Anchoring block to the system prompt
(reduced capitulation 54.7% → 18.7% in published FTM runs). The blocks ship in
the package:

```python
from coesita import ANCHORING_BLOCK, generate_optimized_prompt
```
