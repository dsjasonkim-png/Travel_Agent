"""Flight sub-agent backed by SerpApi when configured."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage

from travel_agent.config import FLIGHT_SERPAPI_API_KEY, OPENAI_API_KEY, get_llm
from travel_agent.slots import format_trip_period, get_departure_city

from .flight_api_client import SerpApiClient

_FALLBACK_PRICE_HINTS = {
    "부산": ("KTX/국내선 비교 권장", ["07:30 출발 | 89,000원", "13:10 출발 | 96,000원"]),
    "도쿄": ("왕복 항공 기준 더미 데이터", ["09:00 출발 | 320,000원", "15:20 출발 | 365,000원"]),
    "제주": ("왕복 항공 기준 더미 데이터", ["08:10 출발 | 74,000원", "18:40 출발 | 92,000원"]),
}

_LOCATION_TO_AIRPORT = {
    "서울": "SEOUL_DEFAULT",
    "seoul": "SEOUL_DEFAULT",
    "인천": "ICN",
    "인천공항": "ICN",
    "인천 국제공항": "ICN",
    "incheon": "ICN",
    "김포": "GMP",
    "김포공항": "GMP",
    "gimpo": "GMP",
    "부산": "PUS",
    "busan": "PUS",
    "김해": "PUS",
    "김해공항": "PUS",
    "gimhae": "PUS",
    "제주": "CJU",
    "제주도": "CJU",
    "제주공항": "CJU",
    "jeju": "CJU",
    "도쿄": "NRT",
    "나리타": "NRT",
    "나리타공항": "NRT",
    "도쿄 나리타": "NRT",
    "tokyo": "NRT",
    "하네다": "HND",
    "하네다공항": "HND",
    "도쿄 하네다": "HND",
    "오사카": "KIX",
    "간사이": "KIX",
    "간사이공항": "KIX",
    "osaka": "KIX",
    "후쿠오카": "FUK",
    "fukuoka": "FUK",
    "삿포로": "CTS",
    "sapporo": "CTS",
    "뉴욕": "JFK",
    "존에프케네디": "JFK",
    "jfk": "JFK",
    "new york": "JFK",
    "로스앤젤레스": "LAX",
    "la": "LAX",
    "los angeles": "LAX",
    "런던": "LHR",
    "히드로": "LHR",
    "히드로공항": "LHR",
    "london": "LHR",
    "파리": "CDG",
    "샤를드골": "CDG",
    "샤를드골공항": "CDG",
    "paris": "CDG",
}

_AGGREGATE_IATA_FALLBACKS = {
    "SEL": "ICN",
    "TYO": "NRT",
    "OSA": "KIX",
    "NYC": "JFK",
    "LON": "LHR",
    "PAR": "CDG",
}
_DOMESTIC_DESTINATION_CODES = {"PUS", "CJU"}
_NOISE_PATTERNS = [
    r"\([^)]*\)",
    r"\b(round trip|one way|flight|flights|airport|airports)\b",
    r"\b(going to|travel to|departing from|departure from|arrival to|from|to)\b",
    r"(국제공항|공항|출발지|도착지|출발|도착|여행지|여행|왕복|편도)",
]
_TRAILING_PARTICLES = (
    "으로",
    "로",
    "에서",
    "으로의",
    "로의",
    "행",
    "가는",
    "가는편",
    "가는 편",
)
_LEADING_PREFIXES = (
    "일본 ",
    "한국 ",
    "대한민국 ",
    "미국 ",
    "영국 ",
    "프랑스 ",
)


def _has_live_flight_api_key() -> bool:
    return bool((FLIGHT_SERPAPI_API_KEY or "").strip())


def _normalize_location(value: str) -> str:
    normalized = (value or "").strip().lower()
    for pattern in _NOISE_PATTERNS:
        normalized = re.sub(pattern, " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"[^\w\s가-힣]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _strip_location_affixes(value: str) -> str:
    stripped = value.strip()
    for prefix in _LEADING_PREFIXES:
        if stripped.startswith(prefix):
            stripped = stripped[len(prefix):].strip()
    changed = True
    while changed and stripped:
        changed = False
        for suffix in _TRAILING_PARTICLES:
            if stripped.endswith(suffix):
                stripped = stripped[: -len(suffix)].strip()
                changed = True
    return stripped


def _clean_display_location(value: str) -> str:
    display = (value or "").strip()
    display = re.sub(r"\([^)]*\)", " ", display)
    display = re.sub(r"(국제공항|공항|출발지|도착지)", " ", display)
    display = re.sub(r"(출발|도착|여행지|여행)", " ", display)
    display = re.sub(r"\s+", " ", display).strip()
    display = _strip_location_affixes(display)
    return display or (value or "").strip()


def _match_location_alias(value: str) -> str:
    if not value:
        return ""

    direct = _LOCATION_TO_AIRPORT.get(value, "")
    if direct:
        return direct

    stripped = _strip_location_affixes(value)
    if stripped != value:
        direct = _LOCATION_TO_AIRPORT.get(stripped, "")
        if direct:
            return direct

    for alias in sorted(_LOCATION_TO_AIRPORT, key=len, reverse=True):
        if alias in value:
            return _LOCATION_TO_AIRPORT[alias]
    if stripped != value:
        for alias in sorted(_LOCATION_TO_AIRPORT, key=len, reverse=True):
            if alias in stripped:
                return _LOCATION_TO_AIRPORT[alias]
    return ""


def _default_seoul_airport(counterpart_code: str = "") -> str:
    counterpart = _AGGREGATE_IATA_FALLBACKS.get(counterpart_code.upper(), counterpart_code.upper())
    if counterpart in _DOMESTIC_DESTINATION_CODES:
        return "GMP"
    return "ICN"


def _extract_json_object(text: str) -> dict[str, Any] | None:
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text) or re.search(r"\{[\s\S]*\}", text)
    if not json_match:
        return None
    raw = json_match.group(1) if "```" in text else json_match.group(0)
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _coerce_airport_code(code: str, counterpart_code: str = "") -> str:
    normalized = (code or "").strip().upper()
    if not normalized:
        return ""
    if normalized == "SEOUL_DEFAULT":
        return _default_seoul_airport(counterpart_code)
    if normalized in _AGGREGATE_IATA_FALLBACKS:
        return _AGGREGATE_IATA_FALLBACKS[normalized]
    if re.fullmatch(r"[A-Z]{3}", normalized):
        return normalized
    return ""


def _resolve_airport_code_with_llm(
    value: str,
    *,
    counterpart_code: str = "",
    role: str,
) -> str:
    if not (OPENAI_API_KEY or "").strip():
        return ""

    normalized_value = _normalize_location(value)
    if not normalized_value:
        return ""

    counterpart = _coerce_airport_code(counterpart_code)
    counterpart_hint = counterpart or "없음"
    prompt = f"""
사용자가 입력한 {role} 위치를 실제 검색 가능한 단일 공항 IATA 코드로 변환하세요.

반드시 JSON 객체 하나만 반환하세요.
형식:
{{
  "airport_code": ""
}}

규칙:
- 3자리 실제 공항 IATA 코드만 반환하세요.
- 도시 묶음 코드(SEL, TYO, NYC, LON, PAR, OSA)는 반환하지 마세요.
- 가장 일반적인 상용 여객 공항 하나를 선택하세요.
- 출발지/도착지 역할과 상대편 공항 코드를 참고해 가장 자연스러운 공항을 고르세요.
- 확신이 없으면 빈 문자열을 반환하세요.

입력 위치: {value}
정규화된 위치: {normalized_value}
역할: {role}
상대편 공항 코드: {counterpart_hint}
""".strip()

    try:
        response = get_llm().invoke([HumanMessage(content=prompt)])
        text = (response.content if hasattr(response, "content") else str(response)).strip()
    except Exception:
        return ""

    data = _extract_json_object(text) or {}
    return _coerce_airport_code(str(data.get("airport_code", "") or ""), counterpart_code)


def _resolve_airport_code(value: str, counterpart_code: str = "") -> str:
    normalized = _normalize_location(value)
    if not normalized:
        return ""

    iata_matches = re.findall(r"\b([A-Za-z]{3})\b", normalized.upper())
    for match in iata_matches:
        if match in _AGGREGATE_IATA_FALLBACKS:
            return _AGGREGATE_IATA_FALLBACKS[match]
        return match

    matched = _match_location_alias(normalized)
    if matched == "SEOUL_DEFAULT":
        return _default_seoul_airport(counterpart_code)
    if matched:
        return matched

    return ""


def _resolve_airport_code_with_fallback(
    value: str,
    *,
    counterpart_code: str = "",
    role: str,
) -> str:
    hardcoded = _resolve_airport_code(value, counterpart_code)
    if hardcoded:
        return hardcoded
    return _resolve_airport_code_with_llm(
        value,
        counterpart_code=counterpart_code,
        role=role,
    )


def _format_price(value: object) -> str:
    if isinstance(value, int):
        return f"{value:,}원"
    if isinstance(value, float):
        return f"{int(value):,}원"
    if value:
        return str(value)
    return "가격 확인 필요"


def _format_live_option(flight: dict[str, object]) -> str:
    segments = flight.get("flights") or []
    if not isinstance(segments, list) or not segments:
        return _format_price(flight.get("price"))

    first_segment = segments[0] if isinstance(segments[0], dict) else {}
    last_segment = segments[-1] if isinstance(segments[-1], dict) else {}
    departure_airport = first_segment.get("departure_airport") or {}
    arrival_airport = last_segment.get("arrival_airport") or {}

    airlines: list[str] = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        airline = str(segment.get("airline") or "").strip()
        if airline and airline not in airlines:
            airlines.append(airline)

    departure_label = str(
        departure_airport.get("id")
        or departure_airport.get("name")
        or "출발지"
    ).strip()
    arrival_label = str(
        arrival_airport.get("id")
        or arrival_airport.get("name")
        or "도착지"
    ).strip()
    departure_time = str(departure_airport.get("time") or "").strip()
    arrival_time = str(arrival_airport.get("time") or "").strip()

    descriptors = [
        _format_price(flight.get("price")),
        ", ".join(airlines) if airlines else "항공사 확인 필요",
        f"{departure_label} {departure_time}".strip(),
        f"{arrival_label} {arrival_time}".strip(),
        "직항" if len(segments) == 1 else f"경유 {len(segments) - 1}회",
    ]

    total_duration = flight.get("total_duration")
    if isinstance(total_duration, int):
        descriptors.append(f"총 {total_duration}분")

    return " | ".join(descriptor for descriptor in descriptors if descriptor)


def _render_dummy_results(slot_values: dict[str, str], reason: str) -> str:
    destination = _clean_display_location((slot_values.get("destination") or "").strip())
    origin = _clean_display_location(get_departure_city(slot_values))
    trip_period = format_trip_period(slot_values)
    note, options = _FALLBACK_PRICE_HINTS.get(
        destination,
        ("왕복 항공 기준 더미 데이터", ["10:00 출발 | 210,000원", "17:00 출발 | 248,000원"]),
    )

    lines = [
        f"{origin} 출발, {destination} 도착 기준 항공 추천입니다.",
        f"일정: {trip_period}",
        reason,
        note,
    ]
    for index, option in enumerate(options, start=1):
        lines.append(f"{index}. {option}")
    return "\n".join(lines)


def _build_live_search_params(slot_values: dict[str, str]) -> tuple[str, str, dict[str, str]]:
    origin = _clean_display_location(get_departure_city(slot_values))
    destination = _clean_display_location((slot_values.get("destination") or "").strip())
    start_date = (slot_values.get("start_date") or "").strip()
    end_date = (slot_values.get("end_date") or "").strip()
    raw_origin = get_departure_city(slot_values)
    raw_destination = (slot_values.get("destination") or "").strip()
    arrival_code = _resolve_airport_code_with_fallback(raw_destination, role="도착지")
    departure_code = _resolve_airport_code_with_fallback(
        raw_origin,
        counterpart_code=arrival_code,
        role="출발지",
    )
    if not arrival_code:
        arrival_code = _resolve_airport_code_with_fallback(
            raw_destination,
            counterpart_code=departure_code,
            role="도착지",
        )

    params = {
        "departure_id": departure_code,
        "arrival_id": arrival_code,
        "outbound_date": start_date,
        "return_date": end_date,
        "type": "1" if end_date else "2",
    }
    return origin, destination, params


def _format_live_results(
    origin: str,
    destination: str,
    trip_period: str,
    data: dict[str, object],
) -> str:
    error = str(data.get("error") or "").strip()
    if error:
        return f"{origin} 출발, {destination} 도착 항공권 조회에 실패했습니다.\n오류: {error}"

    flights = data.get("best_flights") or data.get("other_flights") or []
    if not isinstance(flights, list) or not flights:
        return f"{origin} 출발, {destination} 도착 조건에 맞는 실시간 항공권을 찾지 못했습니다."

    lines = [
        f"{origin} 출발, {destination} 도착 실시간 항공권입니다.",
        f"일정: {trip_period}",
        "SerpApi Google Flights 기준 상위 결과입니다.",
    ]
    for index, flight in enumerate(flights[:3], start=1):
        if not isinstance(flight, dict):
            continue
        lines.append(f"{index}. {_format_live_option(flight)}")
    return "\n".join(lines)


def invoke_flight_agent(slot_values: dict[str, str]) -> str:
    """Return live flight recommendations when SerpApi is configured."""

    destination = (slot_values.get("destination") or "").strip()
    if not destination:
        return "항공 에이전트를 실행하려면 여행지가 필요합니다."

    trip_period = format_trip_period(slot_values)
    if not _has_live_flight_api_key():
        return _render_dummy_results(
            slot_values,
            "flight_serpapi_api_key가 없어 실시간 조회 대신 예시 운임을 표시합니다.",
        )

    origin, _, search_params = _build_live_search_params(slot_values)
    if not search_params["outbound_date"]:
        return "항공권 실시간 조회에는 출발일이 필요합니다."
    if not search_params["departure_id"] or not search_params["arrival_id"]:
        missing_parts: list[str] = []
        if not search_params["departure_id"]:
            missing_parts.append("출발지")
        if not search_params["arrival_id"]:
            missing_parts.append("도착지")
        missing_label = "와 ".join(missing_parts) if len(missing_parts) == 2 else (missing_parts[0] if missing_parts else "위치")
        return (
            f"항공권 조회를 위해 {missing_label} 정보를 조금 더 구체적으로 알려주세요.\n"
            "예: 인천공항, 김포공항, 나리타공항, 하네다공항"
        )

    client = SerpApiClient()
    raw_data = client.fetch_flights(**search_params)
    return _format_live_results(origin, destination, trip_period, raw_data)
