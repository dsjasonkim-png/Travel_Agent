import unittest
from unittest.mock import Mock, patch

from travel_agent.agents.weather import invoke_weather_agent
from travel_agent.agents.weather.tools import get_current_weather


class WeatherAgentTests(unittest.TestCase):
    @patch("travel_agent.agents.weather.tools.OPENWEATHER_API_KEY", "test-key")
    @patch("travel_agent.agents.weather.tools.requests.get")
    def test_current_weather_uses_openweather_api(self, mock_get: Mock) -> None:
        geocoding_response = Mock(status_code=200)
        geocoding_response.json.return_value = [
            {"lat": 35.1796, "lon": 129.0756, "name": "Busan"}
        ]
        weather_response = Mock(status_code=200)
        weather_response.json.return_value = {
            "main": {"temp": 20.4, "humidity": 61},
            "weather": [{"description": "맑음"}],
        }
        mock_get.side_effect = [geocoding_response, weather_response]

        result = get_current_weather.invoke({"location": "Busan"})

        self.assertIn("Busan", result)
        self.assertIn("맑음", result)
        self.assertIn("20.4", result)
        self.assertEqual(mock_get.call_count, 2)

    @patch("travel_agent.agents.weather.agent.OPENAI_API_KEY", "")
    @patch("travel_agent.agents.weather.agent.OPENWEATHER_API_KEY", "configured")
    @patch("travel_agent.agents.weather.agent.get_current_weather")
    @patch("travel_agent.agents.weather.agent.get_weather_forecast")
    def test_weather_agent_falls_back_to_direct_tools(
        self,
        mock_forecast: Mock,
        mock_current: Mock,
    ) -> None:
        mock_current.invoke.return_value = "현재 부산 날씨: 맑음, 기온 20°C, 습도 60%"
        mock_forecast.invoke.return_value = "### 부산 5일 예보\n- 2026-05-01: 19°C, 구름 많음"

        result = invoke_weather_agent(
            {
                "destination": "부산",
                "start_date": "2026-05-01",
                "end_date": "2026-05-03",
            }
        )

        self.assertIn("현재 부산 날씨", result)
        self.assertIn("5일 예보", result)
        mock_current.invoke.assert_called_once_with({"location": "부산"})
        mock_forecast.invoke.assert_called_once_with({"location": "부산"})


if __name__ == "__main__":
    unittest.main()
