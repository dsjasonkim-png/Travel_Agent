"""Dummy hotel sub-agent for the beginner-friendly travel demo."""

from __future__ import annotations

from travel_agent.slots import format_trip_period

_HOTEL_SAMPLES: dict[str, list[dict[str, str]]] = {
    "부산": [
        {"name": "해운대 오션 스테이", "area": "해운대", "price": "1박 14만원"},
        {"name": "광안 브리즈 호텔", "area": "광안리", "price": "1박 11만원"},
    ],
    "도쿄": [
        {"name": "아사쿠사 시티 호텔", "area": "아사쿠사", "price": "1박 16만원"},
        {"name": "신주쿠 라이트 호텔", "area": "신주쿠", "price": "1박 19만원"},
    ],
    "제주": [
        {"name": "제주 코스트 호텔", "area": "제주시", "price": "1박 13만원"},
        {"name": "서귀포 가든 스테이", "area": "서귀포", "price": "1박 12만원"},
    ],
}

_DEFAULT_HOTELS = [
    {"name": "센트럴 시티 호텔", "area": "시내 중심", "price": "1박 12만원"},
    {"name": "트래블 베이직 호텔", "area": "역 근처", "price": "1박 10만원"},
]


def invoke_hotel_agent(slot_values: dict[str, str]) -> str:
    """Return simple dummy hotel recommendations."""

    destination = (slot_values.get("destination") or "").strip()
    if not destination:
        return "호텔 에이전트를 실행하려면 여행지가 필요합니다."

    trip_period = format_trip_period(slot_values)
    hotels = _HOTEL_SAMPLES.get(destination, _DEFAULT_HOTELS)

    lines = [
        f"{destination} 숙소 더미 추천입니다.",
        f"일정: {trip_period}",
    ]
    for index, hotel in enumerate(hotels, start=1):
        lines.append(f"{index}. {hotel['name']} | {hotel['area']} | {hotel['price']}")
    lines.append("실습 단계에서는 API 연동 대신 더미 데이터를 사용합니다.")
    return "\n".join(lines)
