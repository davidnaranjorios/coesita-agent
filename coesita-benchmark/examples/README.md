# Benchmarking real models and agents

There are **two modes** (see the main README): a comparable **model leaderboard**
and an individual **agent evaluation**.

| Example | Mode | Measures |
|---|---|---|
| `run_openai_endpoint.py` | A — model | A model's text STAY/ACT on the fixed FTM corpus (comparable ranking) |
| `run_custom_agent.py` | A — model, custom interface | Same, for a non-OpenAI model interface |
| `run_hermes_agent.py` | **B — agent** | A real agent on scenarios generated from its soul, scored by the actions it actually takes |

In every mode the benchmark drives a 10-turn conversation through a **runner** —
a function `(system_prompt, messages) -> str` (Mode A) or
`-> RunnerResponse(text, tool_calls)` (Mode B, so it can observe real behaviour).
Your agent replies each turn in this format (the system prompt already asks for it):

```
DECISION: STAY        (or ACT)
CONFIDENCE: 7         (1-10)
Reason: one sentence
```

## Mode A — model leaderboard

| Your model is reachable as... | Use | Code needed |
|---|---|---|
| An OpenAI-compatible `/chat/completions` endpoint (hosted model, vLLM, Ollama, LiteLLM, OpenRouter, your own OpenAI-shaped service) | `run_openai_endpoint.py` **or** the `COESITA_BENCHMARK_RUNNERS` env var | none |
| A LangGraph graph / CrewAI crew / Python function / custom HTTP API | `run_custom_agent.py` (write an ~8-line adapter) | a tiny adapter |

## Mode B — agent evaluation (individual)

Use `run_hermes_agent.py` as the reference. The flow:

1. `scan_agent_soul(...)` — ingest the agent's system prompt + tool list.
2. `generate_soul_scenarios(soul, generator=...)` — the agent's **own model**
   generates pressure scenarios in its real domain, using its real tools.
3. The runner returns `RunnerResponse(text, tool_calls)` with the agent's
   tool-call trace (for Hermes, captured via `tool_start_callback`).
4. `evaluate_agent(...)` — scores by what the agent **did** (acted? delegated?
   bypassed the human gate?) and writes an individual report to
   `~/.coesita/benchmark/agents/<slug>.json`, shown on the dashboard's
   **Agents** page.

> Tools must be **enabled** so the benchmark can observe real behaviour. Point
> the agent at a sandbox or mock toolset — `tool_start_callback` fires before
> execution, so a live toolset would actually run side-effecting actions.

## Zero-code path (OpenAI-compatible endpoints)

```bash
export COESITA_BENCHMARK_RUNNERS='{
  "my-agent": {"model": "your-model-id",
               "base_url": "https://your-endpoint/v1",
               "api_key_env": "MY_API_KEY"}
}'
export MY_API_KEY="sk-..."
coesita run --tier standard
coesita dashboard          # -> http://localhost:5050/benchmark
```

## What to expect

- **Cost**: tier `standard` = 30 scenarios x 10 turns = **300 calls per agent**
  (roughly $1-5 of compute depending on model pricing). Use `snapshot` (5
  scenarios, no pressure) for a free smoke test first.
- **Naming**: name your runner after your framework's scan slug (e.g.
  `langgraph`, `crewai`) so the capability-driven feature packs attach to it.
- **Result**: your agent becomes a row between the built-in ceiling
  (data-anchored, CRS 1.000) and floor (social-compliant, CRS ~0.515). A
  healthy real agent lands CRS >= 0.90 / FARP <= 10%. If it drifts, the
  dashboard names the failure archetype and the validated prompt fix.

## Notes for stateful agents

If your agent keeps its own memory between turns, don't re-send the full
history — send only the newest user message and let it remember. See the
`stateful_runner` pattern in `run_custom_agent.py`. Set `max_workers=1` if your
agent isn't thread-safe.
