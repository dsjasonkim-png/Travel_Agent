"""Optional LangGraph wrapper around the hotel sub-agent."""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

from .agent import invoke_hotel_agent


class HotelState(TypedDict, total=False):
    """State used by the optional hotel wrapper graph."""

    query: str
    slot_values: dict[str, str]
    result: str


def run(state: HotelState) -> dict:
    """Execute the hotel sub-agent with either slot values or a legacy query string."""

    slot_values = dict(state.get("slot_values") or {})
    if not slot_values:
        query = state.get("query", "")
        for item in query.split():
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            slot_values[key] = value

        if "check_in" in slot_values and "start_date" not in slot_values:
            slot_values["start_date"] = slot_values["check_in"]
        if "check_out" in slot_values and "end_date" not in slot_values:
            slot_values["end_date"] = slot_values["check_out"]

    return {"result": invoke_hotel_agent(slot_values)}


def get_graph():
    """Return a tiny wrapper graph for compatibility with earlier examples."""

    builder = StateGraph(HotelState)
    builder.add_node("run", run)
    builder.set_entry_point("run")
    builder.add_edge("run", END)
    return builder.compile()
