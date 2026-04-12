"""LangGraph wrapper around the flight sub-agent with optional HITL."""

from __future__ import annotations

from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .agent import invoke_flight_agent


class FlightState(TypedDict, total=False):
    """State used by the optional flight wrapper graph."""

    slot_values: dict[str, str]
    result: str
    current_phase: str


_CHECKPOINTER = InMemorySaver()
_COMPILED_GRAPH = None


def check_origin(_: FlightState) -> dict:
    """Move into the origin-check step."""

    return {"current_phase": "checking_origin"}


def route_origin(state: FlightState) -> str:
    """Route based on whether the departure origin is already known."""

    origin = ((state.get("slot_values") or {}).get("origin") or "").strip()
    if origin:
        return "run"
    return "ask_origin_hitl"


def ask_origin_hitl(state: FlightState) -> dict:
    """Ask for the departure origin before running a live flight search."""

    slot_values = dict(state.get("slot_values") or {})
    destination = (slot_values.get("destination") or "여행지").strip() or "여행지"
    raw_reply = str(
        interrupt(
            {
                "stage": "origin",
                "message": (
                    f"{destination} 항공권을 찾으려면 **출발지**가 필요합니다.\n"
                    "어느 도시나 공항에서 출발하시나요?\n"
                    "예: 서울, 인천, 김포, 부산"
                ),
            }
        )
    ).strip()
    if raw_reply:
        slot_values["origin"] = raw_reply.strip(" .,!?\n\t")
    return {"slot_values": slot_values, "current_phase": "waiting_for_origin"}


def run(state: FlightState) -> dict:
    """Execute the flight sub-agent after required flight info is present."""

    return {"result": invoke_flight_agent(state.get("slot_values") or {})}


def get_graph():
    """Return a compiled flight graph that can ask for a missing origin."""

    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        builder = StateGraph(FlightState)
        builder.add_node("check_origin", check_origin)
        builder.add_node("ask_origin_hitl", ask_origin_hitl)
        builder.add_node("run", run)
        builder.add_edge(START, "check_origin")
        builder.add_conditional_edges(
            "check_origin",
            route_origin,
            {
                "ask_origin_hitl": "ask_origin_hitl",
                "run": "run",
            },
        )
        builder.add_edge("ask_origin_hitl", "check_origin")
        builder.add_edge("run", END)
        _COMPILED_GRAPH = builder.compile(checkpointer=_CHECKPOINTER)
    return _COMPILED_GRAPH
