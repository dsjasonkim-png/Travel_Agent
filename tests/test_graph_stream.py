import logging
import unittest

from travel_agent import graph_stream


class _FakeGraph:
    def __init__(self, events):
        self.events = events
        self.stream_kwargs = None

    def stream(self, input_state, **kwargs):
        self.stream_kwargs = kwargs
        for event in self.events:
            yield event


class GraphStreamTests(unittest.TestCase):
    def test_summarize_update_prefers_key_fields(self) -> None:
        summary = graph_stream._summarize_update(
            {
                "current_phase": "running_subagents",
                "current_service_index": 2,
                "slot_values": {
                    "destination": "도쿄",
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-03",
                },
                "sub_results": {"weather": "ok", "hotel": "ok"},
            }
        )

        self.assertIn("phase=running_subagents", summary)
        self.assertIn("service_index=2", summary)
        self.assertIn("slot_values[destination=\"도쿄\"", summary)
        self.assertIn("sub_results[hotel, weather]", summary)

    def test_run_with_stream_logging_uses_debug_mode_only_when_logger_is_debug(self) -> None:
        graph_stream.logger.setLevel(logging.INFO)
        graph = _FakeGraph(
            [
                ((), "updates", {"collect_trip_details": {"current_phase": "collecting_trip_info"}}),
                ((), "values", {"current_phase": "completed"}),
            ]
        )

        result = graph_stream.run_with_stream_logging(
            graph,
            {"messages": []},
            config={"configurable": {"thread_id": "thread-1"}},
        )

        self.assertEqual(result.get("current_phase"), "completed")
        self.assertEqual(graph.stream_kwargs["stream_mode"], ["updates", "values"])

        graph_stream.logger.setLevel(logging.DEBUG)
        graph_debug = _FakeGraph(
            [
                ((), "updates", {"collect_trip_details": {"current_phase": "collecting_trip_info"}}),
                ((), "debug", {"type": "task", "step": "1", "payload": {"name": "node", "input": {}}}),
                ((), "values", {"current_phase": "completed"}),
            ]
        )

        result_debug = graph_stream.run_with_stream_logging(
            graph_debug,
            {"messages": []},
            config={"configurable": {"thread_id": "thread-2"}},
        )

        self.assertEqual(result_debug.get("current_phase"), "completed")
        self.assertEqual(graph_debug.stream_kwargs["stream_mode"], ["updates", "debug", "values"])


if __name__ == "__main__":
    unittest.main()
