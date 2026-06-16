# Benchmarking a real agent

The benchmark never touches your agent's code. It only needs a **runner** — a
function `(system_prompt, messages) -> str` — and drives a 10-turn conversation
through it, checking whether your agent holds the correct decision as social
pressure mounts while the objective data stays fixed.

Your agent must reply each turn in this format (the system prompt the benchmark
sends already asks for it):

```
DECISION: STAY        (or ACT)
CONFIDENCE: 7         (1-10)
Reason: one sentence
```

## Which example do I use?

| Your agent is reachable as... | Use | Code needed |
|---|---|---|
| An OpenAI-compatible `/chat/completions` endpoint (hosted model, vLLM, Ollama, LiteLLM, OpenRouter, your own OpenAI-shaped service) | `run_openai_endpoint.py` **or** the `COESITA_BENCHMARK_RUNNERS` env var | none |
| A LangGraph graph / CrewAI crew / Python function / custom HTTP API | `run_custom_agent.py` (write an ~8-line adapter) | a tiny adapter |

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
