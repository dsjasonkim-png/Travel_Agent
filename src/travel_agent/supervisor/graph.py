"""슈퍼바이저 그래프: 초기 대화 → 슬롯 결정 → slot filling → 서브 에이전트 라우팅."""

import json
import re

from travel_agent.agents.flight import get_graph as get_flight_graph
from travel_agent.agents.hotel import get_graph as get_hotel_graph
from travel_agent.agents.restaurant import get_graph as get_restaurant_graph
from travel_agent.agents.weather import get_graph as get_weather_graph
from travel_agent.config import get_llm
from travel_agent.state import SupervisorState
from travel_agent.slots import ALL_SLOTS, SLOT_FIELDS, get_active_slots

from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph


def initial_conversation(state: SupervisorState) -> dict:
    """사용자 첫 메시지에 대해 LLM으로 대화 응답 생성."""
    messages = list(state.get("messages") or [])
    if not messages:
        return {"messages": messages, "current_phase": "initial"}
    last_content = (messages[-1].get("content") or "").strip()
    llm = get_llm()
    prompt = (
        "당신은 여행 플래너 어시스턴트입니다. 사용자의 여행 목적/요청을 한 문장으로 친절히 확인하고, "
        "필요한 정보(날씨·호텔·항공·맛집 등)를 안내해 주세요. 한글로만 답하세요.\n\n사용자: " + last_content
    )
    reply = llm.invoke([HumanMessage(content=prompt)])
    content = reply.content if hasattr(reply, "content") else str(reply)
    messages.append({"role": "assistant", "content": content})
    return {"messages": messages, "current_phase": "initial"}


def determine_slots(state: SupervisorState) -> dict:
    """대화 내용을 LLM으로 의도분류해 활성 슬롯 목록 설정."""
    messages = state.get("messages") or []
    last_user = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user = m.get("content", "")
            break
    if not last_user.strip():
        return {"slots": get_active_slots(""), "current_phase": "slot_filling"}

    llm = get_llm()
    prompt = (
        "다음 사용자 메시지에서 여행 플래너가 제공할 서비스 필요 여부를 판단하세요. "
        "필요한 것만 다음 단어만 쉼표로 구분해 답하세요: weather, hotel, flight, restaurant. "
        "맛집/음식/식당이 필요 없다고 하거나 언급이 없으면 restaurant는 제외하세요.\n\n사용자: "
        + (last_user or "").strip()
    )
    out = llm.invoke([HumanMessage(content=prompt)])
    text = (out.content if hasattr(out, "content") else str(out)).strip().lower()
    slots = [s.strip() for s in re.split(r"[,.\s]+", text) if s.strip() in ALL_SLOTS]
    if not slots:
        slots = get_active_slots(last_user)
    return {"slots": slots, "current_phase": "slot_filling"}


def slot_filling(state: SupervisorState) -> dict:
    """대화 내용에서 LLM으로 슬롯 값 추출 (destination, dates, check_in, check_out, origin, preference)."""
    messages = state.get("messages") or []
    slot_values = dict(state.get("slot_values") or {})
    slots = state.get("slots") or []
    # 대화 텍스트 구성
    conv_text = "\n".join(
        f"{m.get('role', '')}: {m.get('content', '')}" for m in messages
    )
    field_names = set()
    for s in slots:
        field_names.update(SLOT_FIELDS.get(s, []))
    if not field_names:
        field_names = {"destination", "dates", "check_in", "check_out", "origin", "preference"}

    llm = get_llm()
    prompt = (
        "다음 대화에서 여행 계획에 필요한 정보를 추출하세요. "
        "아래 키들로 JSON 객체 하나만 출력하세요. 없으면 빈 문자열로 두세요. 다른 설명은 하지 마세요.\n"
        "키: " + ", ".join(sorted(field_names)) + "\n\n대화:\n" + (conv_text or "")
    )
    out = llm.invoke([HumanMessage(content=prompt)])
    text = (out.content if hasattr(out, "content") else str(out)).strip()
    # JSON 블록만 추출 (```json ... ``` 또는 {...})
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text) or re.search(r"\{[\s\S]*\}", text)
    if json_match:
        raw = json_match.group(1) if "```" in text else json_match.group(0)
    else:
        raw = text
    try:
        extracted = json.loads(raw)
        if isinstance(extracted, dict):
            for k, v in extracted.items():
                if k in field_names and v and str(v).strip():
                    slot_values[k] = str(v).strip()
    except json.JSONDecodeError:
        pass
    return {"slot_values": slot_values}


def _query_from_slot_values(slot_values: dict) -> str:
    """slot_values를 서브그래프 query 문자열로 변환."""
    return " ".join(f"{k}={v}" for k, v in (slot_values or {}).items())


_SUB_AGENTS = {
    "weather": get_weather_graph,
    "hotel": get_hotel_graph,
    "flight": get_flight_graph,
    "restaurant": get_restaurant_graph,
}


def invoke_subagents(state: SupervisorState) -> dict:
    """state['slots']에 있는 서브 에이전트만 순서대로 호출하고 결과를 sub_results에 합침."""
    slots = state.get("slots") or []
    slot_values = state.get("slot_values") or {}
    query = _query_from_slot_values(slot_values)
    sub_results = dict(state.get("sub_results") or {})
    for name in slots:
        if name in _SUB_AGENTS:
            graph = _SUB_AGENTS[name]()
            out = graph.invoke({"query": query})
            sub_results[name] = out.get("result", "")
    return {"sub_results": sub_results, "current_phase": "completed"}


def get_supervisor_graph():
    """슈퍼바이저 그래프 빌드 후 컴파일 반환."""
    builder = StateGraph(SupervisorState)

    builder.add_node("initial_conversation", initial_conversation)
    builder.add_node("determine_slots", determine_slots)
    builder.add_node("slot_filling", slot_filling)
    builder.add_node("invoke_subagents", invoke_subagents)

    builder.set_entry_point("initial_conversation")
    builder.add_edge("initial_conversation", "determine_slots")
    builder.add_edge("determine_slots", "slot_filling")
    builder.add_edge("slot_filling", "invoke_subagents")
    builder.add_edge("invoke_subagents", END)

    return builder.compile()
