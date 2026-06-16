#!/usr/bin/env python3
"""Case A — benchmark a real agent exposed via an OpenAI-compatible endpoint.

Works with any /chat/completions endpoint: a hosted model, vLLM, Ollama
(OpenAI compat), LiteLLM proxy, OpenRouter, or your own agent service that
speaks the OpenAI chat protocol.

Run:
    export MY_API_KEY="sk-..."
    python examples/run_openai_endpoint.py
"""

import os

from coesita import make_openai_compatible_runner, run_benchmark

# Point this at YOUR agent's endpoint. The model id is whatever your service
# expects. Name the runner after your framework's scan slug (e.g. "langgraph",
# "crewai") so the capability-driven feature packs match its scan profile.
runner = make_openai_compatible_runner(
    model=os.environ.get("MODEL_ID", "your-model-id"),
    base_url=os.environ.get("BASE_URL", "http://localhost:8000/v1"),
    api_key=os.environ.get("MY_API_KEY"),
)

results = run_benchmark(
    {"my-agent": runner},   # add more runners to compare several at once
    tier="standard",        # 30 scenarios x 10 turns = 300 calls per runner
)

for fw in results["frameworks"]:
    m = fw["metrics"]
    print(
        f"{fw['framework']:>22}  CRS {m['crs']:.3f}  "
        f"FARP {m['farp_strict']:.0%}  PRI {m['pri']:.2f}  "
        f"-> {fw['archetype']['name']}"
    )
print("\nFull report: coesita dashboard  ->  http://localhost:5050/benchmark")
