#!/usr/bin/env python3
"""Evaluate a real Hermes agent INDIVIDUALLY (Mode B — soul + real actions).

This is the reference implementation of agent evaluation:

  1. Read the agent's COMPLETE soul (system prompt + tools).
  2. The agent's OWN backing model generates pressure scenarios in the agent's
     real operational domain, using its real tools.
  3. Run the real Hermes agent with TOOLS ENABLED, capturing its tool-call
     trace each turn via tool_start_callback.
  4. Score by what the agent DID (invoked an action tool? delegated? bypassed
     the human-approval gate?), not by what it said.
  5. Emit an individual report — no cross-agent ranking.

Contrast with Mode A (the model leaderboard): that uses the fixed FTM corpus and
text-only scoring to compare MODELS. Agents are evaluated individually here.

Prerequisites:
  export OPENAI_BASE_URL="http://localhost:30000/v1"   # the agent's model
  export OPENAI_API_KEY="..."
  export HERMES_MODEL="your-model-id"

  Run from the Hermes repo root (so `run_agent` imports) with coesita installed.

SAFETY: tools are ENABLED so the benchmark can observe real behaviour. Point the
agent at a SANDBOX or mock toolset — tool_start_callback fires before execution,
so a real toolset would actually run side-effecting actions during the test.

Run:
    python coesita-benchmark/examples/run_hermes_agent.py
"""

import os

from coesita import (
    evaluate_agent,
    generate_soul_scenarios,
    make_openai_compatible_runner,
    RunnerResponse,
    scan_agent_soul,
)

from run_agent import AIAgent


def introspect_hermes_tools(enabled_toolsets=None) -> list[str]:
    """Read the agent's REAL tool names from Hermes' own registry.

    Uses the same enabled_toolsets the runner will use, so the scored tool
    names match exactly what the agent can emit. Falls back to a representative
    set if the registry can't be loaded (e.g. optional deps missing).
    """
    try:
        from model_tools import get_tool_definitions
        defs = get_tool_definitions(enabled_toolsets=enabled_toolsets, quiet_mode=True)
        names = sorted(t["function"]["name"] for t in defs)
        if names:
            return names
    except Exception as e:  # noqa: BLE001 — introspection is best-effort
        print(f"[warn] tool introspection failed ({e}); using fallback list")
    return ["delegate_task", "execute_code", "terminal", "write_file",
            "patch", "process", "read_file", "search_files", "clarify"]


BASE_URL = os.environ.get("OPENAI_BASE_URL", "http://localhost:30000/v1")
API_KEY = os.environ.get("OPENAI_API_KEY", "")
MODEL = os.environ.get("HERMES_MODEL", "")


def hermes_runner(system_prompt: str, messages: list[dict]) -> RunnerResponse:
    """Drive a real Hermes agent and capture its tool-call trace for the turn."""
    trace: list[dict] = []
    agent = AIAgent(
        base_url=BASE_URL, api_key=API_KEY, model=MODEL,
        enabled_toolsets=None,        # TOOLS ON — we must observe real behaviour
        quiet_mode=True,
        max_iterations=4,             # allow it to actually reach for a tool
        load_soul_identity=True,      # include the SOUL.md identity
        # tool_start_callback(tool_call_id, name, args) — fires before execution
        tool_start_callback=lambda _id, name, args: trace.append(
            {"name": name, "args": args}
        ),
    )
    result = agent.run_conversation(
        user_message=messages[-1]["content"],
        system_message=system_prompt,
        conversation_history=messages[:-1],
    )
    return RunnerResponse(result["final_response"], tool_calls=trace)


if __name__ == "__main__":
    # 1. Ingest the agent's soul (here we read the repo SOUL.md as the system prompt).
    soul_text = ""
    for path in ("SOUL.md", os.path.expanduser("~/.hermes/SOUL.md")):
        if os.path.exists(path):
            soul_text = open(path, encoding="utf-8").read()
            break
    tools = introspect_hermes_tools()   # the agent's REAL tool names
    print(f"Introspected {len(tools)} Hermes tools: {', '.join(tools)}")
    soul = scan_agent_soul("Hermes Agent", slug="hermes",
                           system_prompt=soul_text, tools=tools)

    # 2. The agent's OWN model generates the scenarios (detailed prompt → model-agnostic).
    generator = make_openai_compatible_runner(MODEL, base_url=BASE_URL, api_key=API_KEY)
    scenarios, spec = generate_soul_scenarios(soul, generator=generator, tier="standard")
    print(f"Generated {len(scenarios)} scenarios in domain '{spec['domain']}'. "
          f"Action tool(s): {spec['act_tools']}  Gate: {spec['gate_tool'] or '(none)'}")

    # 3. Evaluate the real agent individually.
    report = evaluate_agent(
        "Hermes Agent", hermes_runner, scenarios, slug="hermes",
        soul_summary={"domain": spec["domain"], "tools": soul["tools"]},
    )

    m, b = report["metrics"], report["behavior"]
    print(f"\nCRS {m['crs']:.3f}  FARP {m['farp_strict']:.0%}  -> {report['archetype']['name']}")
    print(f"Under pressure: acted-without-warrant {b['unwarranted_action_under_pressure']:.0%}, "
          f"gate-bypass {b['gate_bypass_under_pressure']:.0%}, "
          f"delegated {b['delegation_under_pressure']:.0%}")
    print(f"Tools reached for: {b['tools_invoked_freq']}")
    print("\nFull report saved under ~/.coesita/benchmark/agents/hermes.json")
