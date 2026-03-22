"""진입점: 슈퍼바이저 그래프를 더미 입력으로 invoke 테스트."""

import travel_agent.config  # noqa: F401 — .env 로드

from travel_agent.supervisor.graph import get_supervisor_graph


def main() -> None:
    graph = get_supervisor_graph()
    # 목업: 사용자 첫 메시지로 초기 상태 구성 (맛집 제외 예시는 "맛집 필요 없어" 사용)
    initial_state = {
        "messages": [{"role": "user", "content": "서울로 4월에 여행 갈 거예요. 맛집은 필요 없어요."}],
        "slot_values": {},
        "sub_results": {},
    }
    result = graph.invoke(initial_state)
    print("=== Supervisor run (mock) ===")
    print("Slots:", result.get("slots"))
    print("Slot values:", result.get("slot_values"))
    print("Sub results:", result.get("sub_results"))
    print("Phase:", result.get("current_phase"))


if __name__ == "__main__":
    main()
