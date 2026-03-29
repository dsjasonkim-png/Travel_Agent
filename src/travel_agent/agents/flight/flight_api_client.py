import os
from serpapi import GoogleSearch

class SerpApiClient:
    """SerpApi Google Flights 엔진 호출 클라이언트."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.allowed_keys = {
            "departure_id", "arrival_id", "outbound_date", "return_date", "type",
            "currency", "hl", "gl", "travel_class", "adults", "children",
            "stops", "max_price", "outbound_times", "return_times"
        }

    def fetch_flights(self, **kwargs) -> dict:
        """Google Flights 데이터를 요청합니다."""
        if not self.api_key:
            return {"error": "API 키가 설정되지 않았습니다."}

        params = {
            "engine": "google_flights",
            "api_key": self.api_key,
            "currency": "KRW",
            "hl": "ko",
            "gl": "kr",
            "type": kwargs.get("type", "2")
        }

        for k, v in kwargs.items():
            if k in self.allowed_keys and v is not None:
                params[k] = v

        try:
            print(f">>> [API 요청]: Google Flights | {params.get('departure_id')} -> {params.get('arrival_id')}")
            search = GoogleSearch(params)
            return search.get_dict()
        except Exception as e:
            return {"error": f"API 호출 중 예외 발생: {str(e)}"}
