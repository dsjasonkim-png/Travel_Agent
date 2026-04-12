"""Shared state definitions for the travel supervisor graph."""

from typing import TypedDict


class SupervisorState(TypedDict, total=False):
    """State shared across the supervisor workflow."""

    messages: list[dict[str, str]]
    slots: list[str]
    current_service_index: int
    proposed_slots: list[str]
    slot_values: dict[str, str]
    current_phase: str
    sub_results: dict[str, str]


class SubgraphInput(TypedDict, total=False):
    """Compatibility input shape for optional subgraph wrappers."""

    query: str
    slot_values: dict[str, str]
