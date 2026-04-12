from serpapi import GoogleSearch

from travel_agent.config import FLIGHT_SERPAPI_API_KEY

class SerpApiClient:
    """SerpApi Google Flights 엔진 호출 클라이언트."""
    
    def __init__(self, api_key: str | None = None):
        self.api_key = (api_key if api_key is not None else FLIGHT_SERPAPI_API_KEY).strip()
        self.allowed_keys = {
            "departure_id", "arrival_id", "outbound_date", "return_date", "type",
            "currency", "hl", "gl", "travel_class", "adults", "children",
            "stops", "max_price", "outbound_times", "return_times"
        }

    def fetch_flights(self, **kwargs) -> dict:
        """Google Flights 데이터를 요청합니다."""
        if not self.api_key:
            return {"error": "flight_serpapi_api_key가 설정되지 않았습니다."}

        params = {
            "engine": "google_flights",
            "api_key": self.api_key,
            "currency": "KRW",
            "hl": "ko",
            "gl": "kr",
            "type": kwargs.get("type", "2"),
        }

        for k, v in kwargs.items():
            if k in self.allowed_keys and v not in (None, ""):
                params[k] = v

        try:
            search = GoogleSearch(params)
            return search.get_dict()
        except Exception as e:
            return {"error": f"API 호출 중 예외 발생: {str(e)}"}
