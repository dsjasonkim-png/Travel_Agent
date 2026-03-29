"""호텔 서브 에이전트 (서브그래프). 의도분류로 호출 시 호출 확인만 반환."""

from typing import TypedDict

from langgraph.graph import END, StateGraph


class HotelState(TypedDict, total=False):
    """호텔 서브그래프 상태."""

    query: str
    result: str


def run(state: HotelState) -> dict:
    """호출 확인 메시지 반환 후 슈퍼바이저로 복귀."""
    return {"result": "호텔 에이전트가 호출되었습니다."}


def get_graph():
    """컴파일된 호텔 서브그래프 반환. 슈퍼바이저에서 add_node로 등록."""
    builder = StateGraph(HotelState)
    builder.add_node("run", run)
    builder.set_entry_point("run")
    builder.add_edge("run", END)
    return builder.compile()
