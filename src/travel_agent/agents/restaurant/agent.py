from travel_agent.config import SERPAPI_API_KEY
from .tools import get_persona_recommendations

def invoke_restaurant_agent(slot_values: dict[str, str]) -> str:
    """Return live restaurant results using RAG when a SerpApi key exists, otherwise a placeholder message."""

    destination = (slot_values.get("destination") or "").strip()
    travel_context = (slot_values.get("travel_context") or "").strip()

    if not destination:
        return "맛집 에이전트를 실행하려면 여행지가 필요합니다."

    if SERPAPI_API_KEY:
        return get_persona_recommendations(
            location=destination,
            travel_context=travel_context
        )

    return "API 키가 없어 맛집 정보를 찾지 못했습니다."
