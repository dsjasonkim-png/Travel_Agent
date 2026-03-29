import os
import json
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.tools import tool
from travel_agent.config import get_llm
from .flight_api_client import SerpApiClient

load_dotenv()

class FlightSearchTool:
    """항공권 정보를 검색하고 검증하는 도구 클래스."""
    
    def __init__(self):
        self.client = SerpApiClient(os.getenv("flight_serpapi_api_key"))
        self.llm = get_llm()

    def _preprocess_intent(self, query: str) -> Dict[str, Any]:
        """사용자의 요청에서 파라미터(IATA 코드, 날짜 등)를 추출."""
        parser = JsonOutputParser()
        prompt = ChatPromptTemplate.from_messages([
            ("system", "사용자의 요청에서 항공권 검색 파라미터를 JSON으로 추출하세요.\n\n"
                       "### 추출 규칙:\n"
                       "1. departure_id, arrival_id: 지명이 나오면 반드시 3자리 IATA 공항 코드로 변환하세요 (예: 서울->ICN, 뉴욕->JFK).\n"
                       "2. outbound_date: 출발일 (YYYY-MM-DD).\n"
                       "3. return_date: 귀국일 (YYYY-MM-DD). 없으면 빈 문자열.\n"
                       "4. type: 왕복('1'), 편도('2').\n\n"
                       "5. 만약 사용자가 연도를 명시하지 않았다면, 오늘 날짜의 연도를 기준으로 설정하세요.\n"
                       "오늘 날짜: {today}"),
            ("human", "{query}")
        ])
        chain = prompt | self.llm | parser
        try:
            return chain.invoke({"query": query, "today": datetime.now().strftime("%Y-%m-%d")})
        except:
            return {}

    def _format_results(self, data: Dict[str, Any]) -> str:
        """API 결과를 텍스트로 포맷팅."""
        flights = data.get("best_flights", []) or data.get("other_flights", [])
        if not flights:
            return "조건에 맞는 항공권을 찾을 수 없습니다."

        output = ["✈️ **항공권 검색 결과**\n"]
        for i, f in enumerate(flights[:5], 1):
            price = f"{f.get('price', 'N/A'):,}원" if isinstance(f.get('price'), int) else f.get('price', 'N/A')
            details = [f"{s.get('airline')} ({s.get('departure_airport', {}).get('time')}~{s.get('arrival_airport', {}).get('time')})" 
                       for s in f.get("flights", [])]
            output.append(f"{i}. **{price}** | {' ➔ '.join(details)}")

        return "\n".join(output)

    def execute(self, query: str) -> str:
        """파라미터 추출 -> 검증 -> API 호출 -> 포맷팅."""
        try:
            params = self._preprocess_intent(query)
            
            # 필수 값 검증
            if not params.get("departure_id") or not params.get("arrival_id") or not params.get("outbound_date"):
                return "상세 정보를 알려주세요 (출발지, 도착지, 날짜)."

            today = datetime.now().strftime("%Y-%m-%d")
            if params.get("outbound_date") < today:
                return f"날짜({params.get('outbound_date')})가 이미 지났습니다."

            raw_data = self.client.fetch_flights(**params)
            return self._format_results(raw_data)
            
        except Exception as e:
            return f"오류 발생: {str(e)}"

_engine = FlightSearchTool()

@tool
def smart_flight_search(user_query: str) -> str:
    """실시간 항공권을 검색합니다."""
    return _engine.execute(user_query)
