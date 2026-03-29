"""진입점: 슈퍼바이저 그래프 실행 (HITL 시 자동으로 '그대로'로 재개하는 데모)."""

from travel_agent.config import configure_logging
from travel_agent.service import run_agent_turn

configure_logging()


def main() -> None:
    user_messages = [
        ("새 스레드", False, "부산으로 4월에 여행 갈 거예요. 항공이랑 호텔만 알려주세요."),
        ("HITL 답변", True, "그대로 진행해 주세요."),
    ]
    tid: str | None = None
    resume = False
    for label, expect_resume, text in user_messages:
        result, tid, needs = run_agent_turn(tid, text, is_resume=resume)
        print(f"=== {label} ===")
        print("thread_id:", tid[:8] + "…")
        print("needs_resume:", needs)
        if result.get("__interrupt__"):
            v = result["__interrupt__"][0].value
            if isinstance(v, dict):
                print("interrupt_stage:", v.get("stage"))
        else:
            print("Slots:", result.get("slots"))
            print("Destination:", (result.get("slot_values") or {}).get("destination"))
            print("Sub results keys:", list((result.get("sub_results") or {}).keys()))
        resume = needs


if __name__ == "__main__":
    main()
