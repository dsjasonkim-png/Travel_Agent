"""여행 에이전트 실행 로직. Gradio·CLI에서 공통 사용."""

from __future__ import annotations

import uuid
from typing import Any

from langgraph.types import Command

from travel_agent.graph_stream import run_with_stream_logging
from travel_agent.supervisor import get_supervisor_graph


def run_agent_turn(
    thread_id: str | None,
    user_text: str,
    *,
    is_resume: bool = False,
) -> tuple[dict[str, Any], str, bool]:
    """한 턴 실행. HITL 시 `__interrupt__`가 있으면 `needs_resume=True`.

    Returns:
        (result, thread_id, needs_resume)
    """
    graph = get_supervisor_graph()
    tid = thread_id or str(uuid.uuid4())
    config: dict[str, Any] = {"configurable": {"thread_id": tid}}

    if is_resume:
        payload: Any = Command(resume=(user_text or "").strip())
    else:
        payload = {
            "messages": [{"role": "user", "content": (user_text or "").strip()}],
            "slot_values": {},
            "sub_results": {},
        }

    result = run_with_stream_logging(graph, payload, config=config)
    interrupts = result.get("__interrupt__")
    needs_resume = bool(interrupts)
    return result, tid, needs_resume


def run_agent_raw(message: str) -> dict[str, Any]:
    """단일 invoke (체크포인트 없음) — 구버전/간단 테스트용. 매번 새 스레드."""
    result, _, _ = run_agent_turn(None, message, is_resume=False)
    return result
