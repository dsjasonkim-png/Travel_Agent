from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool

from travel_agent.config import FLIGHT_SERPAPI_API_KEY, get_llm

from .flight_api_client import SerpApiClient


class FlightSearchTool:
    """Legacy tool wrapper for direct flight queries."""

    def __init__(self):
        self.client = SerpApiClient(FLIGHT_SERPAPI_API_KEY)
        self.llm = get_llm()

    def _preprocess_intent(self, query: str) -> Dict[str, Any]:
        parser = JsonOutputParser()
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "사용자 요청에서 항공권 검색 파라미터를 JSON으로 추출하세요.\n\n"
                    "규칙:\n"
                    "1. departure_id, arrival_id는 검색 가능한 3자리 공항 IATA 코드여야 합니다.\n"
                    "2. outbound_date는 YYYY-MM-DD 형식입니다.\n"
                    "3. return_date가 없으면 빈 문자열로 둡니다.\n"
                    "4. type은 편도면 '1', 왕복이면 '2'입니다.\n"
                    "5. 날짜가 빠지면 오늘 이후의 가장 가까운 합리적 일정을 추론합니다.\n"
                    "오늘 날짜: {today}",
                ),
                ("human", "{query}"),
            ]
        )
        chain = prompt | self.llm | parser
        try:
            return chain.invoke({"query": query, "today": datetime.now().strftime("%Y-%m-%d")})
        except Exception:
            return {}

    def _format_results(self, data: Dict[str, Any]) -> str:
        flights = data.get("best_flights", []) or data.get("other_flights", [])
        if not flights:
            return "조건에 맞는 항공권을 찾을 수 없습니다."

        lines = ["### 항공권 검색 결과", ""]
        for index, flight in enumerate(flights[:5], start=1):
            raw_price = flight.get("price", "N/A")
            if isinstance(raw_price, int):
                price = f"{raw_price:,}원"
            else:
                price = str(raw_price)

            segments = []
            for segment in flight.get("flights", []):
                airline = segment.get("airline", "항공사 미상")
                departure = segment.get("departure_airport", {}).get("time", "?")
                arrival = segment.get("arrival_airport", {}).get("time", "?")
                segments.append(f"{airline} ({departure}~{arrival})")

            lines.append(f"{index}. **{price}** | {' -> '.join(segments)}")

        return "\n".join(lines)

    def execute(self, query: str) -> str:
        try:
            params = self._preprocess_intent(query)
            if (
                not params.get("departure_id")
                or not params.get("arrival_id")
                or not params.get("outbound_date")
            ):
                return "출발지, 도착지, 날짜를 조금 더 구체적으로 알려주세요."

            today = datetime.now().strftime("%Y-%m-%d")
            if params.get("outbound_date") < today:
                return f"출발일 {params.get('outbound_date')}은 이미 지난 날짜입니다."

            raw_data = self.client.fetch_flights(**params)
            return self._format_results(raw_data)
        except Exception as exc:
            return f"항공권 조회 중 오류가 발생했습니다: {exc}"


_engine = FlightSearchTool()


@tool
def smart_flight_search(user_query: str) -> str:
    """실시간 항공권을 검색합니다."""

    return _engine.execute(user_query)
