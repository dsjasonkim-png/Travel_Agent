"""호텔 서브 에이전트 (서브그래프)."""

import re
from typing import TypedDict

from langgraph.graph import END, StateGraph

from travel_agent.agents.hotel.tools import get_hotel_data_text
from travel_agent.config import SERPAPI_API_KEY


class HotelState(TypedDict, total=False):
    """호텔 서브그래프 상태."""

    query: str
    result: str


def run(state: HotelState) -> dict:
    """문자열 쿼리에서 목적지 및 날짜를 파싱하여 호텔 검색 수행."""
    query = state.get("query", "")
    data = {}
    if query:
        for item in query.split():
            if "=" in item:
                k, v = item.split("=", 1)
                data[k] = v
        
    location = data.get("destination", "").strip()
    check_in = data.get("check_in", "").strip() or data.get("check_in_date", "").strip()
    check_out = data.get("check_out", "").strip() or data.get("check_out_date", "").strip()
    
    if not location:
        return {"result": "⚠️ 여행지(목적지)가 제공되지 않아 호텔을 검색할 수 없습니다."}
        
    # hotels.py 연동 도구 호출
    formatted_result = get_hotel_data_text(
        api_key=SERPAPI_API_KEY, 
        location=location,
        check_in_date=check_in,
        check_out_date=check_out
    )
    
    return {"result": formatted_result}


def get_graph():
    """컴파일된 호텔 서브그래프 반환. 슈퍼바이저에서 add_node로 등록."""
    builder = StateGraph(HotelState)
    builder.add_node("run", run)
    builder.set_entry_point("run")
    builder.add_edge("run", END)
    return builder.compile()
