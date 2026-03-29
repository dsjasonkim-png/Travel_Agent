"""슬롯 정의·동적 결정 로직 (목업). 사용자 목적에 따라 필요한 슬롯을 결정."""

# 고정 슬롯 후보
ALL_SLOTS = ["weather", "hotel", "flight", "restaurant"]

# 슬롯별 필요 필드 (slot_filling에서 참조). 목업용 최소 필드.
SLOT_FIELDS: dict[str, list[str]] = {
    "weather": ["destination", "dates"],
    "hotel": ["destination", "check_in", "check_out"],
    "flight": ["origin", "destination", "dates"],
    "restaurant": ["destination", "dates", "preference"],
}


def get_active_slots(initial_message: str) -> list[str]:
    """초기 사용자 메시지에 따라 활성 슬롯 목록 반환 (목업).

    목업: "맛집 필요 없어", "맛집 제외" 등 키워드 포함 시 restaurant 제외.
    그 외에는 기본 4개 슬롯 모두 포함.
    """
    msg_lower = (initial_message or "").strip().lower()
    # "맛집은 필요 없어요" 등 조사 포함 문장도 매칭
    skip_restaurant_keywords = ["맛집 필요 없", "맛집 제외", "맛집 스킵", "맛집 안 가", "restaurant skip", "no restaurant"]
    if any(kw in msg_lower for kw in skip_restaurant_keywords):
        return [s for s in ALL_SLOTS if s != "restaurant"]
    if "맛집" in msg_lower and ("필요 없" in msg_lower or "제외" in msg_lower or "스킵" in msg_lower):
        return [s for s in ALL_SLOTS if s != "restaurant"]
    return list(ALL_SLOTS)
