"""Weather sub-agent used by the travel supervisor."""

from __future__ import annotations

from typing import Any

from langchain.agents import create_agent

from travel_agent.config import OPENAI_API_KEY, OPENWEATHER_API_KEY, get_llm
from travel_agent.slots import format_trip_period

from .tools import get_current_weather, get_weather_forecast


def _extract_last_message_content(result: dict[str, Any]) -> str:
    messages = result.get("messages") or []
    if not messages:
        return ""

    last_message = messages[-1]
    content = getattr(last_message, "content", last_message)

    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")).strip())
        return "\n".join(part for part in parts if part).strip()
    return str(content).strip()


def invoke_weather_agent(slot_values: dict[str, str]) -> str:
    """Run the weather sub-agent.

    The happy path uses a LangChain agent with OpenWeather tools.
    When the model or network is unavailable, the function falls back to a
    direct tool call or a friendly explanation so the demo still runs.
    """

    destination = (slot_values.get("destination") or "").strip()
    if not destination:
        return "날씨 에이전트를 실행하려면 여행지가 필요합니다."

    trip_period = format_trip_period(slot_values)
    user_prompt = (
        f"여행지: {destination}\n"
        f"여행 일정: {trip_period}\n"
        "현재 날씨와 가까운 시기의 예보를 짧게 요약해 주세요."
    )

    if OPENAI_API_KEY and OPENWEATHER_API_KEY:
        try:
            agent = create_agent(
                model=get_llm(),
                tools=[get_current_weather, get_weather_forecast],
                system_prompt=(
                    "You are a travel weather assistant. "
                    "Use the provided weather tools and answer in Korean. "
                    "Keep the summary short and practical for trip planning."
                ),
                name="weather_agent",
            )
            result = agent.invoke({"messages": [{"role": "user", "content": user_prompt}]})
            final_text = _extract_last_message_content(result)
            if final_text:
                return final_text
        except Exception:
            pass

    if not OPENWEATHER_API_KEY:
        return "날씨 에이전트는 준비됐지만 `OPENWEATHER_API_KEY`가 없어 실제 조회는 건너뜁니다."

    try:
        current = get_current_weather.invoke({"location": destination})
    except Exception as exc:
        current = f"현재 날씨 조회 실패: {exc}"

    try:
        forecast = get_weather_forecast.invoke({"location": destination})
    except Exception as exc:
        forecast = f"예보 조회 실패: {exc}"

    return f"{current}\n{forecast}".strip()
