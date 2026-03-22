"""날씨 서브 에이전트 (서브그래프). 의도분류로 호출 시 호출 확인만 반환."""

from typing import TypedDict

from langgraph.graph import END, StateGraph


class WeatherState(TypedDict, total=False):
    """날씨 서브그래프 상태."""

    query: str
    result: str


def run(state: WeatherState) -> dict:
    """호출 확인 메시지 반환 후 슈퍼바이저로 복귀."""
    return {"result": "날씨 에이전트가 호출되었습니다."}


def get_graph():
    """컴파일된 날씨 서브그래프 반환. 슈퍼바이저에서 add_node로 등록."""
    builder = StateGraph(WeatherState)
    builder.add_node("run", run)
    builder.set_entry_point("run")
    builder.add_edge("run", END)
    return builder.compile()
