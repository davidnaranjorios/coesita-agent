#!/usr/bin/env python3
"""Benchmark a real Hermes agent (the AIAgent class in run_agent.py).

A Hermes agent is a tool-calling loop over a backing model. There are two
things you might want to measure:

  Option 1 (quick): just the backing model's robustness.
      Don't use this file — point COESITA_BENCHMARK_RUNNERS at the same
      base_url/model Hermes uses (see examples/README.md). Zero code.

  Option 2 (this file): the FULL Hermes agent — its system prompt, SOUL
      identity, and reasoning loop. This wraps AIAgent.run_conversation in a
      coesita runner so the benchmark drives the agent through the 10-turn
      pressure conversation and reads its STAY/ACT decisions.

Prerequisites:
  - A backing model endpoint (the agent needs an LLM to reason).
      export OPENAI_BASE_URL="http://localhost:30000/v1"   # or your provider
      export OPENAI_API_KEY="..."
      export HERMES_MODEL="your-model-id"
  - Run this from the Hermes repo root so `run_agent` is importable, with the
    coesita package installed (pip install ./coesita-benchmark).

Run:
    python coesita-benchmark/examples/run_hermes_agent.py
"""

import os

from coesita import run_benchmark

# Import the real Hermes agent from the repo.
from run_agent import AIAgent


def make_hermes_runner() -> "callable":
    """Build a coesita runner backed by a real Hermes AIAgent.

    Toolsets are disabled: FTM measures the *decision* (STAY/ACT expressed in
    text), not real tool execution, so the agent shouldn't run commands during
    the benchmark. The FTM system prompt already instructs the response format.
    """
    base_url = os.environ.get("OPENAI_BASE_URL", "http://localhost:30000/v1")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    model = os.environ.get("HERMES_MODEL", "")

    def runner(system_prompt: str, messages: list[dict]) -> str:
        # Fresh agent per turn = stateless replay of the full conversation.
        # The benchmark accumulates `messages`; the last one is the new turn.
        agent = AIAgent(
            base_url=base_url,
            api_key=api_key,
            model=model,
            enabled_toolsets=[],        # no real tools during the benchmark
            quiet_mode=True,
            max_iterations=1,           # one reasoning turn, then answer
            load_soul_identity=True,    # include the SOUL.md identity (set False to test without it)
        )
        result = agent.run_conversation(
            user_message=messages[-1]["content"],
            system_message=system_prompt,
            conversation_history=messages[:-1],
        )
        return result["final_response"]

    return runner


if __name__ == "__main__":
    results = run_benchmark(
        {"hermes-agent": make_hermes_runner()},   # slug "hermes" -> matches scan profile
        tier="standard",                           # 30 scenarios x 10 turns = 300 turns
        max_workers=2,                             # be gentle on your model endpoint
    )
    for fw in results["frameworks"]:
        m = fw["metrics"]
        print(
            f"{fw['framework']:>22}  CRS {m['crs']:.3f}  "
            f"FARP {m['farp_strict']:.0%}  PRI {m['pri']:.2f}  "
            f"-> {fw['archetype']['name']}"
        )
    print("\nDashboard: coesita dashboard  ->  http://localhost:5050/benchmark")
