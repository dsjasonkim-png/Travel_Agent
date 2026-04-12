"""Optional LangGraph wrapper around the weather sub-agent."""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

from .agent import invoke_weather_agent


class WeatherState(TypedDict, total=False):
    """State used by the optional weather wrapper graph."""

    slot_values: dict[str, str]
    result: str


def run(state: WeatherState) -> dict:
    """Execute the weather sub-agent."""

    return {"result": invoke_weather_agent(state.get("slot_values") or {})}


def get_graph():
    """Return a tiny wrapper graph for compatibility with earlier examples."""

    builder = StateGraph(WeatherState)
    builder.add_node("run", run)
    builder.set_entry_point("run")
    builder.add_edge("run", END)
    return builder.compile()
