"""공유 상태·슬롯 스키마. 슈퍼바이저와 서브그래프 간 주고받는 상태 정의."""

from typing import TypedDict

# 슬롯 타입: 서브 에이전트 도메인
SlotType = str  # "weather" | "hotel" | "flight" | "restaurant"

# 대화 단계
Phase = str


class SupervisorState(TypedDict, total=False):
    """슈퍼바이저 그래프 공유 상태."""

    # 대화 히스토리 (초기 대화 + HITL + slot filling)
    messages: list[dict[str, str]]
    # 최종 서브 에이전트 슬롯 (weather, hotel, flight, restaurant)
    slots: list[str]
    # 의도분류·HITL 확정 전 제안 목록
    proposed_slots: list[str]
    # 슬롯 값 (destination 필수, 기타 도메인별 필드)
    slot_values: dict[str, str]
    current_phase: Phase
    sub_results: dict[str, str]
    # 여행지 없을 때 ask_destination 루프 횟수 (무한 루프 방지)
    destination_loop_count: int


class SubgraphInput(TypedDict, total=False):
    """서브그래프 노드에 넘길 때 사용하는 입력 형태."""

    query: str
    destination: str
    dates: str
