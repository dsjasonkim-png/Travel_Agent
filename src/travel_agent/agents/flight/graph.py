from typing import TypedDict
from langgraph.graph import END, StateGraph
from .tools import smart_flight_search

class FlightState(TypedDict, total=False):
    """항공 서브그래프 상태."""
    query: str
    result: str

def run(state: FlightState) -> dict:
    """항공권 검색 도구를 호출하여 결과를 반환합니다."""
    query = state.get("query", "")
    if not query:
        return {"result": "항공권 검색을 위한 목적지나 날짜 정보가 부족합니다."}
    
    # query는 이미 "서울에서 뉴욕 4월 1일" 등으로 들어옵니다.
    res = smart_flight_search.invoke(query)
    return {"result": res}

def get_graph():
    """컴파일된 항공 서브그래프 반환."""
    builder = StateGraph(FlightState)
    builder.add_node("run", run)
    builder.set_entry_point("run")
    builder.add_edge("run", END)
    return builder.compile()
