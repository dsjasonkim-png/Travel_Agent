"""공유 상태·슬롯 스키마. 슈퍼바이저와 서브그래프 간 주고받는 상태 정의."""

from typing import TypedDict

# 슬롯 타입: 서브 에이전트 도메인
SlotType = str  # "weather" | "hotel" | "flight" | "restaurant"

# 대화 단계
Phase = str  # "initial" | "slot_filling" | "routing" | "completed"


class SupervisorState(TypedDict, total=False):
    """슈퍼바이저 그래프 공유 상태."""

    # 대화 히스토리 (초기 대화 + slot filling). 각 항목: {"role": "user"|"assistant", "content": str}
    messages: list[dict[str, str]]
    # 사용자가 필요로 하는 슬롯 목록 (예: ["weather", "hotel", "flight"] 또는 + "restaurant")
    slots: list[str]
    # 슬롯별로 채워진 값 (예: destination, dates, hotel_preference 등)
    slot_values: dict[str, str]
    # 현재 단계
    current_phase: Phase
    # 서브 에이전트별 결과 (slot 이름 -> 결과 문자열)
    sub_results: dict[str, str]


# 서브그래프에서 사용할 최소 입력 상태 (래퍼에서 변환 시 사용)
class SubgraphInput(TypedDict, total=False):
    """서브그래프 노드에 넘길 때 사용하는 입력 형태 (목업)."""

    query: str
    destination: str
    dates: str
