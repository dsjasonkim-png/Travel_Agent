"""Dummy restaurant sub-agent for the beginner-friendly travel demo."""

from __future__ import annotations

_RESTAURANT_SAMPLES: dict[str, list[str]] = {
    "부산": ["돼지국밥 골목", "해운대 횟집 거리", "광안리 브런치 카페"],
    "도쿄": ["스시 오마카세", "라멘 전문점", "이자카야 거리"],
    "제주": ["흑돼지 식당", "갈치조림 맛집", "오션뷰 카페"],
}

_DEFAULT_RESTAURANTS = ["현지 인기 식당", "시장 골목 식당", "동네 브런치 카페"]


def invoke_restaurant_agent(slot_values: dict[str, str]) -> str:
    """Return simple dummy restaurant recommendations."""

    destination = (slot_values.get("destination") or "").strip()
    if not destination:
        return "맛집 에이전트를 실행하려면 여행지가 필요합니다."

    restaurants = _RESTAURANT_SAMPLES.get(destination, _DEFAULT_RESTAURANTS)
    lines = [f"{destination} 맛집 더미 추천입니다."]
    for index, name in enumerate(restaurants, start=1):
        lines.append(f"{index}. {name}")
    lines.append("실습 단계에서는 지도 API 대신 지역별 예시 데이터를 사용합니다.")
    return "\n".join(lines)
