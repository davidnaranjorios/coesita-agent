#!/usr/bin/env python3
"""Case B — benchmark a real agent that has its OWN interface.

If your agent is a LangGraph graph, a CrewAI crew, a plain Python function, or
a custom HTTP API that is NOT OpenAI-shaped, you don't need to change your
agent. You write a small adapter: a function

    runner(system_prompt: str, messages: list[dict]) -> str

that (1) hands the conversation to your agent however it works, and
(2) returns the agent's reply as text. The benchmark drives a 10-turn
conversation and parses each reply for:

    DECISION: STAY|ACT
    CONFIDENCE: 1-10
    Reason: <one sentence>

The system_prompt the benchmark passes ALREADY instructs that exact format, so
if your agent forwards the system prompt to its underlying model, it will
comply. If your agent returns a structured decision instead, just format it
into those three lines yourself (see `format_decision` below).

Run:
    python examples/run_custom_agent.py
"""

import threading

from coesita import run_benchmark


def format_decision(decision: str, confidence: int, reason: str) -> str:
    """Turn a structured decision into the three lines the benchmark parses."""
    return f"DECISION: {decision}\nCONFIDENCE: {confidence}\nReason: {reason}"


# ── Option 1: STATELESS agent (a pure function of the conversation) ───────────
# The benchmark accumulates the full chat history in `messages` and re-sends it
# every turn. This is the simplest case and parallelizes safely.
def stateless_runner(system_prompt: str, messages: list[dict]) -> str:
    # Replace this block with a real call to your agent:
    #   reply = my_agent.invoke(system=system_prompt, history=messages)
    #   return reply              # if it already returns the FTM format
    # or, if your agent returns a structured result:
    #   out = my_agent.decide(system_prompt, messages)
    #   return format_decision(out.action, out.confidence, out.rationale)
    raise NotImplementedError("Wire stateless_runner to your agent")


# ── Option 2: STATEFUL agent (keeps its own memory across turns) ──────────────
# If your agent maintains internal state (a session, a graph checkpoint, a
# persistent memory), don't re-send the whole history — send only the newest
# user message and let the agent remember. Each scenario's 10 turns run
# sequentially on one worker thread, so we key the session by thread id and
# reset it on turn 1 (when there is exactly one user message).
_sessions: dict[int, object] = {}


def _new_session(system_prompt: str) -> object:
    # return my_framework.new_session(system_prompt=system_prompt)
    raise NotImplementedError("Wire _new_session to your agent")


def _send(session: object, user_message: str) -> str:
    # return session.send(user_message)   # must return the FTM-format reply
    raise NotImplementedError("Wire _send to your agent")


def stateful_runner(system_prompt: str, messages: list[dict]) -> str:
    turn = sum(1 for m in messages if m["role"] == "user")
    tid = threading.get_ident()

    if turn == 1:  # new scenario on this worker -> fresh session
        _sessions[tid] = _new_session(system_prompt)

    return _send(_sessions[tid], messages[-1]["content"])


if __name__ == "__main__":
    # Pick whichever adapter matches your agent and wire it up above.
    results = run_benchmark(
        {"my-agent": stateless_runner},   # name -> your scan slug for feature packs
        tier="standard",
        max_workers=4,        # set to 1 if your stateful agent isn't thread-safe
    )
    for fw in results["frameworks"]:
        m = fw["metrics"]
        print(
            f"{fw['framework']:>22}  CRS {m['crs']:.3f}  "
            f"FARP {m['farp_strict']:.0%}  -> {fw['archetype']['name']}"
        )
