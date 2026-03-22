"""Gradio 챗봇 UI: 여행 에이전트와 대화하고 결과를 확인합니다."""

from __future__ import annotations

import json
from typing import Any

import gradio as gr

from travel_agent.config import configure_logging
from travel_agent.service import run_agent_turn

configure_logging()


def _chat_messages_from_result(result: dict[str, Any]) -> list[dict[str, str]]:
    """체크포인트 상태 messages + interrupt 안내 문구를 Gradio Chatbot 형식으로."""
    out: list[dict[str, str]] = []
    for m in result.get("messages") or []:
        role = m.get("role", "")
        content = (m.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            out.append({"role": role, "content": content})
    for intr in result.get("__interrupt__") or []:
        val = getattr(intr, "value", intr)
        if isinstance(val, dict):
            msg = (val.get("message") or "").strip()
            if msg:
                out.append({"role": "assistant", "content": msg})
    return out


def _summary_markdown(result: dict[str, Any]) -> str:
    lines = []
    if result.get("__interrupt__"):
        lines.append("**상태:** 사용자 입력 대기 (Human-in-the-loop)")
        for intr in result["__interrupt__"]:
            val = getattr(intr, "value", intr)
            if isinstance(val, dict) and val.get("stage"):
                lines.append(f"- **단계:** `{val['stage']}`")
    else:
        lines.append("**상태:** 실행 완료")
    lines.append("")
    lines.append("**Slots:** " + ", ".join(result.get("slots") or []))
    if result.get("proposed_slots"):
        lines.append("**제안(slots 확정 전):** " + ", ".join(result["proposed_slots"]))
    lines.append("**Phase:** " + str(result.get("current_phase", "")))
    lines.append("")
    lines.append("**Slot values:**")
    lines.append(
        "```json\n"
        + json.dumps(result.get("slot_values") or {}, ensure_ascii=False, indent=2)
        + "\n```"
    )
    lines.append("")
    lines.append("**Sub results:**")
    for name, value in (result.get("sub_results") or {}).items():
        lines.append(f"- **{name}:** {value}")
    return "\n".join(lines)


def build_ui() -> gr.Blocks:
    with gr.Blocks() as demo:
        gr.Markdown("# 여행 에이전트 테스트")
        gr.Markdown(
            "여행 목적을 입력하면 **여행지 확인 → 필요 서비스 확인(HITL)** 후 서브 에이전트가 호출됩니다. "
            "중간에 질문이 나오면 답한 뒤 다시 **Enter**로 보내 주세요."
        )

        thread_id_state = gr.State(value=None)
        waiting_resume_state = gr.State(value=False)

        with gr.Row():
            with gr.Column(scale=2):
                chatbot = gr.Chatbot(label="대화", height=420)
                msg = gr.Textbox(
                    label="메시지",
                    placeholder="첫 메시지 또는 HITL 답변을 입력… (Enter로 전송)",
                    lines=1,
                    autofocus=True,
                )
                submit_btn = gr.Button("실행")

            with gr.Column(scale=1):
                state_summary = gr.Markdown(
                    label="결과 요약",
                    value="실행 후 슬롯·상태가 여기 표시됩니다.",
                )

        def submit(
            user_input: str,
            thread_id: str | None,
            waiting_resume: bool,
            chat_hist: list,
            summary_md: str,
        ):
            if not (user_input or "").strip():
                return chat_hist, summary_md, "", thread_id, waiting_resume

            if waiting_resume:
                result, tid, needs = run_agent_turn(thread_id, user_input, is_resume=True)
            else:
                result, tid, needs = run_agent_turn(None, user_input, is_resume=False)

            chat = _chat_messages_from_result(result)
            summary = _summary_markdown(result)
            return chat, summary, "", tid, needs

        io = [msg, thread_id_state, waiting_resume_state, chatbot, state_summary]
        outputs = [chatbot, state_summary, msg, thread_id_state, waiting_resume_state]
        msg.submit(submit, inputs=io, outputs=outputs)
        submit_btn.click(submit, inputs=io, outputs=outputs)

        gr.Markdown("---\n*`.env`의 `OPENAI_MODEL`(기본 gpt-4o-mini)이 사용됩니다.*")
    return demo


def main() -> None:
    demo = build_ui()
    demo.launch()


if __name__ == "__main__":
    main()
