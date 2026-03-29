"""날씨 서브 에이전트 (서브그래프). 의도분류로 호출 시 호출 확인만 반환."""

from typing import TypedDict
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import create_react_agent
from travel_agent.config import get_llm
from travel_agent.agents.weather.tools import get_current_weather, get_weather_forecast

class WeatherState(TypedDict, total=False):
    """날씨 서브그래프 상태."""
    query: str
    result: str

def run(state: WeatherState) -> dict:
    """슈퍼바이저가 준 query를 바탕으로 ReAct 에이전트를 실행하고 결과를 result에 담습니다."""
    query = state.get("query", "")
    if not query:
        return {"result": "날씨 조회를 위한 정보가 부족합니다."}

    llm = get_llm()
    tools = [get_current_weather, get_weather_forecast]
    
    # 시스템 프롬프트 설정 (기존 weather_agent.py 참고)
    system_prompt = (
        "당신은 여행 기상 전문가 에이전트입니다.\n"
        "1. 제공된 정보(query)에 지역명이 있으면 즉시 도구를 호출하여 날씨나 예보를 확인하세요.\n"
        "2. 지역명이 없거나 불분명하면 사용자에게 질문하세요.\n"
        "3. [지역명] 날씨 정보 형식으로 요약해서 친절하게 답변하세요."
    )
    
    agent = create_react_agent(llm, tools, prompt=system_prompt)
    
    # 쿼리 내용을 사용자 메시지로 전달
    inputs = {"messages": [("user", f"현재 여행 계획 정보: {query}\n이 정보를 바탕으로 날씨 안내를 해주세요.")]}
    try:
        response = agent.invoke(inputs)
        # 마지막 메시지가 AI의 응답
        ai_msg = response["messages"][-1].content
        return {"result": ai_msg}
    except Exception as e:
        return {"result": f"날씨 에이전트 실행 중 오류가 발생했습니다: {str(e)}"}

def get_graph():
    """컴파일된 날씨 서브그래프 반환."""
    builder = StateGraph(WeatherState)
    builder.add_node("run", run)
    builder.set_entry_point("run")
    builder.add_edge("run", END)
    return builder.compile()
