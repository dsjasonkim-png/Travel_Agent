"""Optional LangGraph wrapper around the restaurant sub-agent."""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

from .agent import invoke_restaurant_agent


class RestaurantState(TypedDict, total=False):
    """State used by the optional restaurant wrapper graph."""

    slot_values: dict[str, str]
    result: str


def run(state: RestaurantState) -> dict:
    """Execute the restaurant sub-agent."""

    return {"result": invoke_restaurant_agent(state.get("slot_values") or {})}


def get_graph():
    """Return a tiny wrapper graph for compatibility with earlier examples."""

    builder = StateGraph(RestaurantState)
    builder.add_node("run", run)
    builder.set_entry_point("run")
    builder.add_edge("run", END)
    return builder.compile()
