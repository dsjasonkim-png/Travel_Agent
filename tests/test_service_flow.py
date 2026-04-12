import unittest
from unittest.mock import patch

from travel_agent.config import OPENAI_API_KEY
from travel_agent.service import run_agent_raw, run_agent_turn
from travel_agent.supervisor import chapter_graph as supervisor_graph


class ServiceFlowHitlTests(unittest.TestCase):
    def setUp(self) -> None:
        supervisor_graph._COMPILED_GRAPH = None

    def tearDown(self) -> None:
        supervisor_graph._COMPILED_GRAPH = None

    @patch.dict(
        supervisor_graph._SUB_AGENTS,
        {
            "weather": lambda slot_values: f"weather:{slot_values.get('destination')}",
            "hotel": lambda slot_values: f"hotel:{slot_values.get('destination')}",
            "flight": lambda slot_values: f"flight:{slot_values.get('origin')}->{slot_values.get('destination')}",
            "restaurant": lambda slot_values: f"restaurant:{slot_values.get('destination')}",
        },
        clear=True,
    )
    def test_run_agent_turn_interrupts_for_origin_during_flight_step(self) -> None:
        result, _, needs_resume = run_agent_turn(
            None,
            "도쿄로 2026-05-01부터 2026-05-03까지 여행 가고 싶어요.",
        )

        self.assertTrue(needs_resume)
        self.assertIn("__interrupt__", result)
        self.assertEqual(result.get("current_service_index"), 2)
        self.assertEqual((result.get("sub_results") or {}).get("weather"), "weather:도쿄")
        self.assertEqual((result.get("sub_results") or {}).get("hotel"), "hotel:도쿄")
        self.assertNotIn("flight", result.get("sub_results") or {})

    @patch.dict(
        supervisor_graph._SUB_AGENTS,
        {
            "weather": lambda slot_values: f"weather:{slot_values.get('destination')}",
            "hotel": lambda slot_values: f"hotel:{slot_values.get('destination')}",
            "flight": lambda slot_values: f"flight:{slot_values.get('origin')}->{slot_values.get('destination')}",
            "restaurant": lambda slot_values: f"restaurant:{slot_values.get('destination')}",
        },
        clear=True,
    )
    def test_run_agent_turn_resumes_after_origin_reply(self) -> None:
        _, thread_id, needs_resume = run_agent_turn(
            None,
            "도쿄로 2026-05-01부터 2026-05-03까지 여행 가고 싶어요.",
        )
        self.assertTrue(needs_resume)

        resumed, _, resumed_needs_resume = run_agent_turn(
            thread_id,
            "서울",
            is_resume=True,
        )

        self.assertFalse(resumed_needs_resume)
        self.assertEqual(resumed.get("current_phase"), "completed")
        self.assertEqual((resumed.get("slot_values") or {}).get("origin"), "서울")
        self.assertEqual((resumed.get("sub_results") or {}).get("flight"), "flight:서울->도쿄")
        self.assertEqual((resumed.get("sub_results") or {}).get("restaurant"), "restaurant:도쿄")


@unittest.skipUnless(OPENAI_API_KEY, "OPENAI_API_KEY is required for the live extraction test.")
class ServiceFlowTests(unittest.TestCase):
    def test_run_agent_raw_completes_when_trip_info_is_present(self) -> None:
        result = run_agent_raw("서울에서 출발해서 부산으로 2026-05-01부터 2026-05-03까지 여행 가고 싶어요.")

        self.assertEqual(result.get("current_phase"), "completed")
        self.assertEqual((result.get("slot_values") or {}).get("destination"), "부산")
        self.assertEqual((result.get("slot_values") or {}).get("start_date"), "2026-05-01")
        self.assertEqual((result.get("slot_values") or {}).get("end_date"), "2026-05-03")
        self.assertEqual((result.get("slot_values") or {}).get("origin"), "서울")
        self.assertEqual(result.get("slots"), ["weather", "hotel", "flight", "restaurant"])
        self.assertIn("weather", result.get("sub_results") or {})


if __name__ == "__main__":
    unittest.main()
