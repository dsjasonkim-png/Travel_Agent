import os
import requests
import json
from datetime import datetime
from langchain_core.tools import tool

# 환경 변수 로드 (이미 supervisor에서 수행되지만 여기에서도 안전을 위해 확인 가능)
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
GEOCODING_URL = "https://api.openweathermap.org/geo/1.0/direct"
CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

def get_coordinates(city_name: str):
    """도시 이름을 위도/경도로 변환"""
    print(f"[Debug] get_coordinates called with: {city_name}")
    if not OPENWEATHER_API_KEY:
        print("[Debug] Error: OPENWEATHER_API_KEY is missing")
        return None, None, None
    
    params = {"q": city_name, "limit": 1, "appid": OPENWEATHER_API_KEY}
    try:
        res = requests.get(GEOCODING_URL, params=params)
        print(f"[Debug] Geocoding API response status: {res.status_code}")
        if res.status_code == 200 and res.json():
            data = res.json()[0]
            print(f"[Debug] Geocoding success: {data.get('name')} ({data.get('lat')}, {data.get('lon')})")
            return data["lat"], data["lon"], data["name"]
        else:
            print(f"[Debug] Geocoding failed or empty: {res.text}")
    except Exception as e:
        print(f"[Debug] Geocoding Exception: {e}")
    return None, None, None

@tool
def get_current_weather(location: str) -> str:
    """특정 지역의 현재 날씨(온도, 습도, 풍속 등)를 조회합니다."""
    print(f"[Debug] get_current_weather tool called for: {location}")
    if not OPENWEATHER_API_KEY:
        return "OpenWeather API Key가 설정되지 않았습니다."
        
    lat, lon, city = get_coordinates(location)
    if not lat: 
        return f"'{location}'을 찾을 수 없습니다."
    
    params = {
        "lat": lat, 
        "lon": lon, 
        "appid": OPENWEATHER_API_KEY, 
        "units": "metric", 
        "lang": "kr"
    }
    try:
        res = requests.get(CURRENT_URL, params=params)
        if res.status_code != 200:
            return f"API 호출 오류 (코트: {res.status_code})"
        data = res.json()
        
        main, w = data['main'], data['weather'][0]
        return f"현재 {city} 날씨: {w['description']}, 기온 {main['temp']}°C, 습도 {main['humidity']}%"
    except Exception as e:
        return f"날씨 조회 중 오류 발생: {str(e)}"

@tool
def get_weather_forecast(location: str) -> str:
    """특정 지역의 향후 5일간 일기예보를 조회합니다."""
    if not OPENWEATHER_API_KEY:
        return "OpenWeather API Key가 설정되지 않았습니다."

    lat, lon, city = get_coordinates(location)
    if not lat: 
        return f"'{location}'을 찾을 수 없습니다."

    params = {
        "lat": lat, 
        "lon": lon, 
        "appid": OPENWEATHER_API_KEY, 
        "units": "metric", 
        "lang": "kr"
    }
    try:
        res = requests.get(FORECAST_URL, params=params)
        if res.status_code != 200:
            return f"API 호출 오류 (코드: {res.status_code})"
        data = res.json()
        
        output = [f"### {city} 5일 예보"]
        current_date = ""
        for item in data.get('list', []):
            dt_day = datetime.fromtimestamp(item['dt']).strftime("%Y-%m-%d")
            if dt_day != current_date:
                current_date = dt_day
                output.append(f"- {dt_day}: {item['main']['temp']}°C, {item['weather'][0]['description']}")
        return "\n".join(output)
    except Exception as e:
        return f"일기예보 조회 중 오류 발생: {str(e)}"
