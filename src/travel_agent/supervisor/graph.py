"""슈퍼바이저 그래프: 초기 대화 → 여행지 확보(HITL) → 서비스 슬롯 확인(HITL) → slot filling → 서브 에이전트."""

from __future__ import annotations

import json
import re

from travel_agent.agents.flight import get_graph as get_flight_graph
from travel_agent.agents.hotel import get_graph as get_hotel_graph
from travel_agent.agents.restaurant import get_graph as get_restaurant_graph
from travel_agent.agents.weather import get_graph as get_weather_graph
from travel_agent.agents.flight import invoke_flight_agent
from travel_agent.agents.hotel import invoke_hotel_agent
from travel_agent.agents.restaurant import invoke_restaurant_agent
from travel_agent.agents.weather import invoke_weather_agent
from travel_agent.config import get_llm
from travel_agent.slots import ALL_SLOTS, SLOT_FIELDS
from travel_agent.slots import SERVICE_ORDER, missing_trip_fields
from travel_agent.state import SupervisorState
from travel_agent.supervisor.llm_utils import invoke_text, parse_json_object

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

# 프로세스 전체에서 스레드별 체크포인트 유지 (Gradio 멀티 턴 HITL)
_CHECKPOINTER = InMemorySaver()
_COMPILED_GRAPH = None


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


def extract_destination(state: SupervisorState) -> dict:
    """대화에서 여행지(destination) 추출. 없으면 빈 값."""
    messages = state.get("messages") or []
    conv = "\n".join(f"{m.get('role', '')}: {m.get('content', '')}" for m in messages)
    prompt = (
        "다음 대화에서 사용자가 **가고 싶어 하는 여행 목적지**(도시/국가/지역 이름)가 있으면 JSON만 출력하세요.\n"
        '형식: {"destination": "도시명"} 또는 알 수 없으면 {"destination": ""}\n'
        "추상적 표현만 있고 구체적 지명이 없으면 destination은 빈 문자열.\n\n대화:\n" + conv
    )
    text = invoke_text(prompt)
    data = parse_json_object(text) or {}
    dest = str(data.get("destination", "") or "").strip()
    slot_values = dict(state.get("slot_values") or {})
    if dest:
        slot_values["destination"] = dest
    return {"slot_values": slot_values, "destination_loop_count": 0, "current_phase": "destination"}


def route_has_destination(state: SupervisorState) -> str:
    if (state.get("slot_values") or {}).get("destination", "").strip():
        return "draft_service_slots"
    return "ask_destination_hitl"


def ask_destination_hitl(state: SupervisorState) -> dict:
    """Human-in-the-loop: 여행지 확인 또는 추천 요청."""
    reply = interrupt(
        {
            "stage": "destination",
            "message": (
                "가고 싶은 **여행지**(도시·지역 이름)를 알려 주세요.\n\n"
                "아직 정하지 못하셨다면 **추천**이라고만 입력해 주시면, 대화 맥락에 맞춰 여행지를 제안해 드릴게요."
            ),
        }
    )
    messages = list(state.get("messages") or [])
    messages.append({"role": "user", "content": str(reply).strip()})
    count = int(state.get("destination_loop_count") or 0) + 1
    return {"messages": messages, "destination_loop_count": count}


def process_destination_reply(state: SupervisorState) -> dict:
    """사용자 답변: 추천 요청 vs 지명 vs 불명확 처리."""
    messages = list(state.get("messages") or [])
    last = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last = (m.get("content") or "").strip()
            break
    slot_values = dict(state.get("slot_values") or {})
    low = last.lower()

    # 키워드: 추천
    if "추천" in last or "recommend" in low or "suggest" in low:
        conv = "\n".join(f"{m.get('role', '')}: {m.get('content', '')}" for m in messages)
        prompt = (
            "사용자가 여행지 추천을 요청했습니다. 대화 맥락을 반영해 **한 곳**의 여행지(도시/지역)를 한글로 짧게 추천하세요.\n"
            'JSON만 출력: {"destination": "추천 도시명", "assistant_reply": "사용자에게 보여줄 1~2문장 친절한 설명"}\n\n'
            "대화:\n" + conv
        )
        text = invoke_text(prompt)
        data = parse_json_object(text) or {}
        dest = str(data.get("destination", "") or "").strip()
        ar = str(data.get("assistant_reply", "") or "").strip() or f"{dest}(으)로 다녀오시는 건 어떨까요?"
        if dest:
            slot_values["destination"] = dest
        messages.append({"role": "assistant", "content": ar})
        return {"slot_values": slot_values, "messages": messages}

    prompt = (
        "사용자의 마지막 메시지에서 여행 **목적지** 도시/지역 이름을 추출하세요. 없으면 빈 문자열.\n"
        'JSON만: {"destination": "도시명 또는 빈 문자열", "unclear": true/false}\n'
        "unclear는 지명이 없거나 애매할 때 true.\n\n사용자: " + last
    )
    text = invoke_text(prompt)
    data = parse_json_object(text) or {}
    dest = str(data.get("destination", "") or "").strip()
    unclear = bool(data.get("unclear", False))
    if dest:
        slot_values["destination"] = dest
        return {"slot_values": slot_values, "messages": messages}
    if unclear or not last:
        messages.append(
            {
                "role": "assistant",
                "content": "여행지 이름을 알려 주시거나, 정하지 못하셨다면 **추천**이라고 입력해 주세요.",
            }
        )
        return {"slot_values": slot_values, "messages": messages}
    return {"slot_values": slot_values, "messages": messages}


def route_after_destination(state: SupervisorState) -> str:
    if (state.get("slot_values") or {}).get("destination", "").strip():
        return "draft_service_slots"
    if int(state.get("destination_loop_count") or 0) >= 4:
        return "force_destination_default"
    return "ask_destination_hitl"


def force_destination_default(state: SupervisorState) -> dict:
    """루프 초과 시 기본 여행지 부여 (실습용)."""
    slot_values = dict(state.get("slot_values") or {})
    if not slot_values.get("destination", "").strip():
        slot_values["destination"] = "서울"
    messages = list(state.get("messages") or [])
    messages.append(
        {
            "role": "assistant",
            "content": "여행지 응답이 여러 번 확인되지 않아, 우선 **서울**을 기본 여행지로 두고 진행할게요. 나중에 바꾸고 싶으시면 말씀해 주세요.",
        }
    )
    return {"slot_values": slot_values, "messages": messages}


def draft_service_slots(state: SupervisorState) -> dict:
    """대화만으로 필요해 보이는 서비스(weather/hotel/flight/restaurant) 초안."""
    messages = state.get("messages") or []
    conv = "\n".join(f"{m.get('role', '')}: {m.get('content', '')}" for m in messages)
    prompt = (
        "여행 플래너가 제공할 수 있는 항목은 weather(날씨), hotel(호텔), flight(항공), restaurant(맛집) 네 가지입니다.\n"
        "대화만 보고 사용자에게 **필요해 보이는** 항목만 골라 JSON 배열로 출력하세요. "
        "**예를 들어,** 맛집이 필요 없다고 하면 restaurant는 넣지 마세요.\n"
        '형식: {"proposed_slots": ["flight", "hotel", ...]}\n\n대화:\n' + conv
    )
    text = invoke_text(prompt)
    data = parse_json_object(text) or {}
    raw = data.get("proposed_slots", [])
    if not isinstance(raw, list):
        raw = []
    proposed = [str(x).strip().lower() for x in raw if str(x).strip().lower() in ALL_SLOTS]
    if not proposed:
        proposed = list(ALL_SLOTS)
    return {"proposed_slots": proposed, "current_phase": "slot_confirm"}


def confirm_slots_hitl(state: SupervisorState) -> dict:
    """Human-in-the-loop: 제안된 서비스 외 날씨·맛집 등 필요 여부 확인."""
    proposed = list(state.get("proposed_slots") or [])
    missing = [s for s in ALL_SLOTS if s not in proposed]
    labels = {"weather": "날씨", "hotel": "호텔", "flight": "항공", "restaurant": "맛집"}
    prop_kr = ", ".join(labels.get(s, s) for s in proposed)
    miss_kr = ", ".join(labels.get(s, s) for s in missing) if missing else "(없음)"

    msg = (
        f"지금까지 대화로는 **{prop_kr}** 정도만 도와드리면 될 것 같아요.\n\n"
        f"그 외 **{miss_kr}** 도 필요하신가요?\n"
        "- 필요한 항목이 있으면 이름을 적어 주세요 (예: 날씨도, 맛집도).\n"
        "- **아니요** 또는 **그대로** 라고 하시면 위 제안만으로 진행할게요."
    )
    reply = interrupt({"stage": "slot_confirm", "message": msg, "proposed_slots": proposed})
    messages = list(state.get("messages") or [])
    messages.append({"role": "user", "content": str(reply).strip()})
    return {"messages": messages}


def finalize_slots(state: SupervisorState) -> dict:
    """사용자 확인 답변을 반영해 최종 slots 확정."""
    proposed = list(state.get("proposed_slots") or [])
    messages = state.get("messages") or []
    last = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last = (m.get("content") or "").strip()
            break
    conv_tail = "\n".join(f"{m.get('role', '')}: {m.get('content', '')}" for m in messages[-6:])
    prompt = (
        "제안된 서비스 목록(영문 키): " + ", ".join(proposed) + "\n"
        "가능한 키: weather, hotel, flight, restaurant.\n"
        "사용자의 마지막 답변을 반영해 **최종적으로 제공할** 키 목록을 JSON으로만 출력하세요.\n"
        '형식: {"slots": ["weather", "hotel", ...]}\n'
        "사용자가 '아니요', '그대로', '괜찮아요' 등이면 proposed_slots를 그대로 쓰세요.\n"
        "추가를 원하면 해당 키를 proposed에 합치세요.\n\n"
        f"사용자 마지막 답변: {last}\n최근 대화:\n{conv_tail}"
    )
    text = invoke_text(prompt)
    data = parse_json_object(text) or {}
    raw = data.get("slots", proposed)
    if not isinstance(raw, list):
        raw = proposed
    slots = [str(x).strip().lower() for x in raw if str(x).strip().lower() in ALL_SLOTS]
    if not slots:
        slots = proposed if proposed else list(ALL_SLOTS)
    return {"slots": slots, "current_phase": "slot_filling"}


def slot_filling(state: SupervisorState) -> dict:
    """선택된 slots에 맞춰 대화에서 부가 정보 추출."""
    messages = state.get("messages") or []
    slot_values = dict(state.get("slot_values") or {})
    slots = state.get("slots") or []
    conv_text = "\n".join(f"{m.get('role', '')}: {m.get('content', '')}" for m in messages)
    field_names: set[str] = {"destination"}
    for s in slots:
        field_names.update(SLOT_FIELDS.get(s, []))

    llm = get_llm()
    prompt = (
        "다음 대화에서 여행 계획에 필요한 정보를 추출하세요. "
        "아래 키들로 JSON 객체 하나만 출력하세요. 없으면 빈 문자열.\n"
        "키: " + ", ".join(sorted(field_names)) + "\n\n대화:\n" + (conv_text or "")
    )
    out = llm.invoke([HumanMessage(content=prompt)])
    text = (out.content if hasattr(out, "content") else str(out)).strip()
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
    return " ".join(f"{k}={v}" for k, v in (slot_values or {}).items())


_SUB_AGENTS = {
    "weather": get_weather_graph,
    "hotel": get_hotel_graph,
    "flight": get_flight_graph,
    "restaurant": get_restaurant_graph,
}


def _format_subagent_reply_for_user(slots: list[str], sub_results: dict[str, str]) -> str:
    """Gradio 등 UI는 `messages`만 챗에 표시하므로, 서브 에이전트 결과를 assistant 발화로 만든다."""
    labels = {"weather": "날씨", "hotel": "호텔", "flight": "항공", "restaurant": "맛집"}
    lines: list[str] = []
    for name in slots:
        if name not in sub_results:
            continue
        text = (sub_results.get(name) or "").strip()
        if not text:
            continue
        title = labels.get(name, name)
        lines.append(f"[{title}]\n{text}")
    if lines:
        return "요청하신 정보입니다.\n\n" + "\n\n".join(lines)
    if slots:
        return "선택하신 서비스를 처리했지만, 표시할 결과 문구가 없습니다. (서브 에이전트 `result` 확인)"
    return "호출된 서비스가 없습니다."


def invoke_subagents(state: SupervisorState) -> dict:
    slots = state.get("slots") or []
    slot_values = state.get("slot_values") or {}
    query = _query_from_slot_values(slot_values)
    sub_results = dict(state.get("sub_results") or {})
    for name in slots:
        if name in _SUB_AGENTS:
            graph = _SUB_AGENTS[name]()
            out = graph.invoke({"query": query})
            sub_results[name] = out.get("result", "")
    messages = list(state.get("messages") or [])
    messages.append(
        {
            "role": "assistant",
            "content": _format_subagent_reply_for_user(slots, sub_results),
        }
    )
    return {
        "sub_results": sub_results,
        "current_phase": "completed",
        "messages": messages,
    }


def _build_graph() -> StateGraph:
    builder = StateGraph(SupervisorState)

    builder.add_node("initial_conversation", initial_conversation)
    builder.add_node("extract_destination", extract_destination)
    builder.add_node("ask_destination_hitl", ask_destination_hitl)
    builder.add_node("process_destination_reply", process_destination_reply)
    builder.add_node("force_destination_default", force_destination_default)
    builder.add_node("draft_service_slots", draft_service_slots)
    builder.add_node("confirm_slots_hitl", confirm_slots_hitl)
    builder.add_node("finalize_slots", finalize_slots)
    builder.add_node("slot_filling", slot_filling)
    builder.add_node("invoke_subagents", invoke_subagents)

    builder.add_edge(START, "initial_conversation")
    builder.add_edge("initial_conversation", "extract_destination")
    builder.add_conditional_edges(
        "extract_destination",
        route_has_destination,
        {
            "ask_destination_hitl": "ask_destination_hitl",
            "draft_service_slots": "draft_service_slots",
        },
    )
    builder.add_edge("ask_destination_hitl", "process_destination_reply")
    builder.add_conditional_edges(
        "process_destination_reply",
        route_after_destination,
        {
            "ask_destination_hitl": "ask_destination_hitl",
            "draft_service_slots": "draft_service_slots",
            "force_destination_default": "force_destination_default",
        },
    )
    builder.add_edge("force_destination_default", "draft_service_slots")
    builder.add_edge("draft_service_slots", "confirm_slots_hitl")
    builder.add_edge("confirm_slots_hitl", "finalize_slots")
    builder.add_edge("finalize_slots", "slot_filling")
    builder.add_edge("slot_filling", "invoke_subagents")
    builder.add_edge("invoke_subagents", END)

    return builder


def get_supervisor_graph():
    """체크포인터가 붙은 컴파일된 슈퍼바이저 그래프 (HITL용 싱글톤)."""
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = _build_graph().compile(checkpointer=_CHECKPOINTER)
    return _COMPILED_GRAPH


# ---------------------------------------------------------------------------
# Beginner-friendly implementation used by the current chapter demo.
# LangGraph is kept only for slot collection + interrupt loops.
# Sub-agents are called directly as plain callables.
# ---------------------------------------------------------------------------

_CHECKPOINTER = InMemorySaver()
_COMPILED_GRAPH = None

_DATE_PATTERN = re.compile(r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})")
_DESTINATION_PATTERNS = [
    re.compile(r"([가-힣A-Za-z]{2,}?(?:\s[가-힣A-Za-z]{2,}?)?)\s*(?:으로|로)"),
    re.compile(r"([가-힣A-Za-z]{2,}?(?:\s[가-힣A-Za-z]{2,}?)?)\s*(?:으로|로)\s*(?:여행|가|떠나)"),
    re.compile(r"(?:destination|dest)\s*[:=]\s*([가-힣A-Za-z\s]+)", re.IGNORECASE),
    re.compile(r"(?:to|visit|going to)\s+([A-Za-z][A-Za-z\s]+)", re.IGNORECASE),
]
_ORIGIN_PATTERNS = [
    re.compile(r"([가-힣A-Za-z]{2,}(?:\s[가-힣A-Za-z]{2,})?)\s*에서 출발"),
    re.compile(r"from\s+([A-Za-z][A-Za-z\s]+)", re.IGNORECASE),
]

_SUB_AGENTS = {
    "weather": invoke_weather_agent,
    "hotel": invoke_hotel_agent,
    "flight": invoke_flight_agent,
    "restaurant": invoke_restaurant_agent,
}

_SERVICE_LABELS = {
    "weather": "날씨",
    "hotel": "호텔",
    "flight": "항공",
    "restaurant": "맛집",
}


def _normalize_date(year: str, month: str, day: str) -> str:
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _extract_dates(text: str) -> tuple[str, str]:
    matches = [_normalize_date(*match) for match in _DATE_PATTERN.findall(text)]
    unique_matches: list[str] = []
    for item in matches:
        if item not in unique_matches:
            unique_matches.append(item)

    if len(unique_matches) >= 2:
        return unique_matches[0], unique_matches[1]
    return "", ""


def _extract_destination(text: str) -> str:
    stripped = (text or "").strip()

    for pattern in _DESTINATION_PATTERNS:
        match = pattern.search(stripped)
        if match:
            return match.group(1).strip(" .,!?\n\t")

    if stripped and not re.search(r"\d", stripped) and len(stripped) <= 20 and " " not in stripped:
        return stripped

    return ""


def _extract_origin(text: str) -> str:
    stripped = (text or "").strip()
    for pattern in _ORIGIN_PATTERNS:
        match = pattern.search(stripped)
        if match:
            return match.group(1).strip(" .,!?\n\t")
    return ""


def _extract_trip_details(
    messages: list[dict[str, str]],
    existing: dict[str, str] | None = None,
) -> dict[str, str]:
    slot_values = dict(existing or {})

    for message in messages:
        if message.get("role") != "user":
            continue

        content = message.get("content", "")

        if not slot_values.get("destination"):
            destination = _extract_destination(content)
            if destination:
                slot_values["destination"] = destination

        if not slot_values.get("origin"):
            origin = _extract_origin(content)
            if origin:
                slot_values["origin"] = origin

        if not slot_values.get("start_date") or not slot_values.get("end_date"):
            start_date, end_date = _extract_dates(content)
            if start_date and end_date:
                slot_values["start_date"] = start_date
                slot_values["end_date"] = end_date

    return slot_values


def _format_subagent_reply_for_user(slots: list[str], sub_results: dict[str, str]) -> str:
    lines = ["여행 준비 결과입니다."]
    for name in slots:
        result = (sub_results.get(name) or "").strip()
        if not result:
            continue
        label = _SERVICE_LABELS.get(name, name)
        lines.append(f"\n[{label}]\n{result}")
    return "\n".join(lines).strip()


def initial_conversation(state: SupervisorState) -> dict:
    """Append a simple beginner-friendly introduction."""

    messages = list(state.get("messages") or [])
    has_assistant_message = any(message.get("role") == "assistant" for message in messages)
    if not has_assistant_message:
        messages.append(
            {
                "role": "assistant",
                "content": (
                    "여행지와 날짜가 정해질 때까지 먼저 확인한 뒤, "
                    "날씨 -> 호텔 -> 항공 -> 맛집 순서로 정리해 드릴게요."
                ),
            }
        )
    return {"messages": messages, "current_phase": "collecting_trip_info"}


def collect_trip_details(state: SupervisorState) -> dict:
    """Extract destination, dates, and optional origin from user messages."""

    messages = list(state.get("messages") or [])
    slot_values = _extract_trip_details(messages, state.get("slot_values"))
    return {"slot_values": slot_values, "current_phase": "collecting_trip_info"}


def _needs_flight_origin(slot_values: dict[str, str]) -> bool:
    """Return whether the current flight step still needs a departure origin."""

    return not (slot_values.get("origin") or "").strip()


def route_trip_details(state: SupervisorState) -> str:
    """Route based on required trip info."""

    slot_values = state.get("slot_values") or {}
    missing_fields = missing_trip_fields(slot_values)
    if "destination" in missing_fields:
        return "ask_destination_hitl"
    if "start_date" in missing_fields or "end_date" in missing_fields:
        return "ask_dates_hitl"
    return "prepare_services"


def ask_destination_hitl(state: SupervisorState) -> dict:
    """Ask for the destination when it is missing."""

    reply = interrupt(
        {
            "stage": "destination",
            "message": "어디로 여행 가시나요? 예: 부산, 도쿄, 제주",
        }
    )
    messages = list(state.get("messages") or [])
    messages.append({"role": "user", "content": str(reply).strip()})
    return {"messages": messages, "current_phase": "waiting_for_destination"}


def ask_dates_hitl(state: SupervisorState) -> dict:
    """Ask for exact travel dates when they are missing."""

    destination = (state.get("slot_values") or {}).get("destination", "여행지")
    reply = interrupt(
        {
            "stage": "dates",
            "message": (
                f"{destination} 여행 날짜를 알려주세요.\n"
                "초보자용 실습이라 `YYYY-MM-DD` 형식이 가장 잘 동작합니다.\n"
                "예: 2026-05-01부터 2026-05-03까지"
            ),
        }
    )
    messages = list(state.get("messages") or [])
    messages.append({"role": "user", "content": str(reply).strip()})
    return {"messages": messages, "current_phase": "waiting_for_dates"}


def ask_origin_hitl(state: SupervisorState) -> dict:
    """Ask for the current flight step's departure city when it is missing."""

    destination = (state.get("slot_values") or {}).get("destination", "여행지")
    raw_reply = str(
        interrupt(
            {
                "stage": "origin",
                "message": (
                    f"{destination} 항공권을 찾으려면 **출발지**가 필요합니다.\n"
                    "어느 도시나 공항에서 출발하시나요?\n"
                    "예: 서울, 인천, 김포, 부산"
                ),
            }
        )
    ).strip()
    normalized_reply = raw_reply.strip(" .,!?\n\t")
    messages = list(state.get("messages") or [])
    messages.append({"role": "user", "content": raw_reply})

    slot_values = dict(state.get("slot_values") or {})
    if normalized_reply:
        slot_values["origin"] = normalized_reply

    return {
        "messages": messages,
        "slot_values": slot_values,
        "current_phase": "waiting_for_origin",
    }


def prepare_services(state: SupervisorState) -> dict:
    """Freeze the fixed service order used in the chapter demo."""

    return {
        "slots": list(SERVICE_ORDER),
        "current_service_index": 0,
        "current_phase": "running_subagents",
    }


def check_current_service(state: SupervisorState) -> dict:
    """Enter the current service orchestration step."""

    return {"current_phase": "running_subagents"}


def _get_current_service_name(state: SupervisorState) -> str:
    slots = list(state.get("slots") or SERVICE_ORDER)
    index = int(state.get("current_service_index") or 0)
    if 0 <= index < len(slots):
        return slots[index]
    return ""


def route_current_service(state: SupervisorState) -> str:
    """Route to the next service, a service-specific HITL step, or completion."""

    service_name = _get_current_service_name(state)
    if not service_name:
        return "finalize_subagent_results"
    if service_name == "flight" and _needs_flight_origin(state.get("slot_values") or {}):
        return "ask_origin_hitl"
    return "execute_current_service"


def execute_current_service(state: SupervisorState) -> dict:
    """Execute exactly one sub-agent, then advance to the next service."""

    slots = list(state.get("slots") or SERVICE_ORDER)
    service_index = int(state.get("current_service_index") or 0)
    if service_index >= len(slots):
        return {}

    name = slots[service_index]
    slot_values = dict(state.get("slot_values") or {})
    sub_results: dict[str, str] = {}
    sub_results.update(state.get("sub_results") or {})

    handler = _SUB_AGENTS.get(name)
    if handler is None:
        sub_results[name] = f"{_SERVICE_LABELS.get(name, name)} 에이전트가 등록되지 않았습니다."
    else:
        try:
            sub_results[name] = handler(slot_values)
        except Exception as exc:
            sub_results[name] = f"{_SERVICE_LABELS.get(name, name)} 에이전트 실행 실패: {exc}"

    return {
        "sub_results": sub_results,
        "current_service_index": service_index + 1,
        "current_phase": f"completed_{name}",
    }


def finalize_subagent_results(state: SupervisorState) -> dict:
    """Append the aggregated sequential service results to the chat."""

    slots = list(state.get("slots") or SERVICE_ORDER)
    messages = list(state.get("messages") or [])
    messages.append(
        {
            "role": "assistant",
            "content": _format_subagent_reply_for_user(slots, state.get("sub_results") or {}),
        }
    )

    return {
        "messages": messages,
        "current_phase": "completed",
    }


def _build_graph() -> StateGraph:
    builder = StateGraph(SupervisorState)

    builder.add_node("initial_conversation", initial_conversation)
    builder.add_node("collect_trip_details", collect_trip_details)
    builder.add_node("ask_destination_hitl", ask_destination_hitl)
    builder.add_node("ask_dates_hitl", ask_dates_hitl)
    builder.add_node("ask_origin_hitl", ask_origin_hitl)
    builder.add_node("prepare_services", prepare_services)
    builder.add_node("check_current_service", check_current_service)
    builder.add_node("execute_current_service", execute_current_service)
    builder.add_node("finalize_subagent_results", finalize_subagent_results)

    builder.add_edge(START, "initial_conversation")
    builder.add_edge("initial_conversation", "collect_trip_details")
    builder.add_conditional_edges(
        "collect_trip_details",
        route_trip_details,
        {
            "ask_destination_hitl": "ask_destination_hitl",
            "ask_dates_hitl": "ask_dates_hitl",
            "ask_origin_hitl": "ask_origin_hitl",
            "prepare_services": "prepare_services",
        },
    )
    builder.add_edge("ask_destination_hitl", "collect_trip_details")
    builder.add_edge("ask_dates_hitl", "collect_trip_details")
    builder.add_edge("prepare_services", "check_current_service")
    builder.add_conditional_edges(
        "check_current_service",
        route_current_service,
        {
            "ask_origin_hitl": "ask_origin_hitl",
            "execute_current_service": "execute_current_service",
            "finalize_subagent_results": "finalize_subagent_results",
        },
    )
    builder.add_edge("ask_origin_hitl", "check_current_service")
    builder.add_edge("execute_current_service", "check_current_service")
    builder.add_edge("finalize_subagent_results", END)

    return builder


def get_supervisor_graph():
    """Return the compiled supervisor graph with checkpointing."""

    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = _build_graph().compile(checkpointer=_CHECKPOINTER)
    return _COMPILED_GRAPH
