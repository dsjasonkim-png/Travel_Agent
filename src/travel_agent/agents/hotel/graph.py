"""Optional LangGraph wrapper around the hotel sub-agent."""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

from .agent import invoke_hotel_agent


class HotelState(TypedDict, total=False):
    """State used by the optional hotel wrapper graph."""

    slot_values: dict[str, str]
    result: str


def run(state: HotelState) -> dict:
    """Execute the hotel sub-agent."""

    return {"result": invoke_hotel_agent(state.get("slot_values") or {})}


def get_graph():
    """Return a tiny wrapper graph for compatibility with earlier examples."""

    builder = StateGraph(HotelState)
    builder.add_node("run", run)
    builder.set_entry_point("run")
    builder.add_edge("run", END)
    return builder.compile()
