import unittest
from unittest.mock import patch

from travel_agent.agents.flight import invoke_flight_agent
from travel_agent.agents.flight.agent import (
    _build_live_search_params,
    _resolve_airport_code,
    _resolve_airport_code_with_fallback,
)
from travel_agent.agents.flight.graph import get_graph
from travel_agent.agents.flight import graph as flight_graph_module
from langgraph.types import Command


class FlightAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        flight_graph_module._COMPILED_GRAPH = None

    def tearDown(self) -> None:
        flight_graph_module._COMPILED_GRAPH = None

    @patch("travel_agent.agents.flight.agent.OPENAI_API_KEY", "configured")
    @patch("travel_agent.agents.flight.agent.get_llm")
    def test_resolve_airport_code_uses_llm_when_hardcoded_alias_misses(self, mock_get_llm: object) -> None:
        class _FakeResponse:
            content = '{"airport_code": "SFO"}'

        class _FakeLLM:
            def invoke(self, _: object) -> _FakeResponse:
                return _FakeResponse()

        mock_get_llm.return_value = _FakeLLM()

        self.assertEqual(
            _resolve_airport_code_with_fallback("샌프란시스코 다운타운", role="도착지"),
            "SFO",
        )

    def test_resolve_airport_code_accepts_natural_location_variants(self) -> None:
        self.assertEqual(_resolve_airport_code("서울에서", counterpart_code="NRT"), "ICN")
        self.assertEqual(_resolve_airport_code("서울 출발", counterpart_code="CJU"), "GMP")
        self.assertEqual(_resolve_airport_code("인천공항"), "ICN")
        self.assertEqual(_resolve_airport_code("도쿄로"), "NRT")
        self.assertEqual(_resolve_airport_code("일본 도쿄"), "NRT")
        self.assertEqual(_resolve_airport_code("도쿄 (TYO)"), "NRT")
        self.assertEqual(_resolve_airport_code("제주도"), "CJU")

    def test_live_search_params_use_searchable_airports_for_major_cities(self) -> None:
        _, _, params = _build_live_search_params(
            {
                "origin": "서울",
                "destination": "도쿄",
                "start_date": "2026-05-01",
                "end_date": "2026-05-03",
            }
        )

        self.assertEqual(params["departure_id"], "ICN")
        self.assertEqual(params["arrival_id"], "NRT")
        self.assertEqual(params["type"], "1")

    @patch("travel_agent.agents.flight.graph.invoke_flight_agent", return_value="flight:서울->도쿄")
    def test_flight_graph_interrupts_and_resumes_when_origin_is_missing(self, _: object) -> None:
        graph = get_graph()
        config = {"configurable": {"thread_id": "flight-graph-origin"}}

        interrupted = graph.invoke(
            {
                "slot_values": {
                    "destination": "도쿄",
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-03",
                }
            },
            config=config,
        )

        self.assertIn("__interrupt__", interrupted)

        resumed = graph.invoke(Command(resume="서울"), config=config)

        self.assertEqual((resumed.get("slot_values") or {}).get("origin"), "서울")
        self.assertEqual(resumed.get("result"), "flight:서울->도쿄")

    @patch("travel_agent.agents.flight.agent.SerpApiClient.fetch_flights")
    @patch("travel_agent.agents.flight.agent._has_live_flight_api_key", return_value=True)
    def test_live_flight_response_mentions_live_results(self, _: object, mock_fetch: object) -> None:
        mock_fetch.return_value = {
            "best_flights": [
                {
                    "price": 210000,
                    "total_duration": 135,
                    "flights": [
                        {
                            "airline": "대한항공",
                            "departure_airport": {"id": "ICN", "time": "08:10"},
                            "arrival_airport": {"id": "TYO", "time": "10:25"},
                        }
                    ],
                }
            ]
        }

        result = invoke_flight_agent(
            {
                "destination": "도쿄",
                "start_date": "2026-05-01",
                "end_date": "2026-05-03",
                "origin": "서울",
            }
        )

        self.assertIn("도쿄", result)
        self.assertIn("서울", result)
        self.assertIn("실시간 항공권", result)
        self.assertIn("대한항공", result)
        self.assertIn("210,000원", result)

    @patch("travel_agent.agents.flight.agent._resolve_airport_code_with_fallback", return_value="")
    @patch("travel_agent.agents.flight.agent._has_live_flight_api_key", return_value=True)
    def test_flight_agent_returns_generic_prompt_when_location_is_still_ambiguous(
        self,
        _: object,
        __: object,
    ) -> None:
        result = invoke_flight_agent(
            {
                "destination": "어딘가 외곽 지역",
                "start_date": "2026-05-01",
                "end_date": "2026-05-03",
                "origin": "어딘가 도심",
            }
        )

        self.assertIn("조금 더 구체적으로", result)
        self.assertNotIn("공항 코드로 변환", result)

    @patch("travel_agent.agents.flight.agent._has_live_flight_api_key", return_value=False)
    def test_flight_agent_falls_back_to_dummy_when_key_is_missing(self, _: object) -> None:
        result = invoke_flight_agent(
            {
                "destination": "부산",
                "start_date": "2026-05-01",
                "end_date": "2026-05-03",
                "origin": "서울",
            }
        )

        self.assertIn("부산", result)
        self.assertIn("서울", result)
        self.assertIn("예시 운임", result)


if __name__ == "__main__":
    unittest.main()
