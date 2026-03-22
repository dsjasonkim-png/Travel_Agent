"""여행 에이전트 실행 로직. FastAPI·Gradio에서 공통 사용."""

from travel_agent.supervisor.graph import get_supervisor_graph


def run_agent_raw(message: str) -> dict:
    """사용자 메시지로 슈퍼바이저를 한 번 실행하고, 전체 상태 dict 반환."""
    graph = get_supervisor_graph()
    initial_state = {
        "messages": [{"role": "user", "content": (message or "").strip()}],
        "slot_values": {},
        "sub_results": {},
    }
    return graph.invoke(initial_state)
