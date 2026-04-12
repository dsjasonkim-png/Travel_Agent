"""Simplified supervisor graph used in the final book chapter demo."""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from travel_agent.agents.flight import invoke_flight_agent
from travel_agent.agents.hotel import invoke_hotel_agent
from travel_agent.agents.restaurant import invoke_restaurant_agent
from travel_agent.agents.weather import invoke_weather_agent
from travel_agent.slots import SERVICE_ORDER, missing_trip_fields
from travel_agent.state import SupervisorState
from travel_agent.supervisor.llm_utils import invoke_text, parse_json_object

_CHECKPOINTER = InMemorySaver()
_COMPILED_GRAPH = None

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


def _conversation_as_text(messages: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for message in messages:
        role = message.get("role", "").strip() or "unknown"
        content = (message.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _extract_trip_details(
    messages: list[dict[str, str]],
    existing: dict[str, str] | None = None,
) -> dict[str, str]:
    slot_values = dict(existing or {})
    conversation = _conversation_as_text(messages)

    prompt = f"""
다음 대화에서 여행 계획 슬롯을 추출하세요.

반드시 JSON 객체 하나만 반환하세요.
형식:
{{
  "destination": "",
  "start_date": "",
  "end_date": "",
  "origin": ""
}}

규칙:
- destination: 여행지 도시/지역명
- start_date, end_date: 정확히 알 수 있을 때만 YYYY-MM-DD
- origin: 출발지가 명시된 경우만 채우기
- 알 수 없으면 빈 문자열
- 이미 채워진 값이 있으면 그 값을 유지하고, 새 정보가 더 명확할 때만 보완

현재 알고 있는 값:
{slot_values}

대화:
{conversation}
""".strip()

    data = parse_json_object(invoke_text(prompt)) or {}
    for field in ("destination", "start_date", "end_date", "origin"):
        value = str(data.get(field, "") or "").strip()
        if value:
            slot_values[field] = value

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
