"""Gradio 챗봇 UI: 여행 에이전트와 대화하고 결과를 확인합니다."""

import json

import gradio as gr

import travel_agent.config  # noqa: F401 — .env 로드
from travel_agent.service import run_agent_raw


def run_agent(user_message: str) -> tuple[list[tuple[str | None, str | None]], str]:
    """사용자 메시지로 에이전트를 실행하고, UI용 채팅 히스토리·상태 요약 반환."""
    if not (user_message or "").strip():
        return [(None, "메시지를 입력해 주세요.")], ""

    result = run_agent_raw(user_message.strip())

    # 채팅: 사용자 메시지 + 어시스턴트 첫 응답
    messages = result.get("messages") or []
    chat_history: list[tuple[str | None, str | None]] = []
    for m in messages:
        role, content = m.get("role", ""), m.get("content", "")
        if role == "user":
            chat_history.append((content, None))
        elif role == "assistant" and content:
            if chat_history and chat_history[-1][1] is None:
                chat_history[-1] = (chat_history[-1][0], content)
            else:
                chat_history.append((None, content))

    # 상태 요약 (테스트용)
    summary_lines = [
        "**Slots:** " + ", ".join(result.get("slots") or []),
        "**Phase:** " + str(result.get("current_phase", "")),
        "",
        "**Slot values:**",
        "```json\n" + json.dumps(result.get("slot_values") or {}, ensure_ascii=False, indent=2) + "\n```",
        "",
        "**Sub results:**",
    ]
    for name, value in (result.get("sub_results") or {}).items():
        summary_lines.append(f"- **{name}:** {value}")
    summary = "\n".join(summary_lines)

    return chat_history, summary


def build_ui() -> gr.Blocks:
    """Gradio 블록 UI 구성."""
    with gr.Blocks() as demo:
        gr.Markdown("# 여행 에이전트 테스트")
        gr.Markdown("여행 목적을 입력하면 슬롯 결정·서브 에이전트 결과를 확인할 수 있습니다.")

        with gr.Row():
            with gr.Column(scale=2):
                chatbot = gr.Chatbot(label="대화", height=400)
                msg = gr.Textbox(
                    label="메시지",
                    placeholder="예: 서울로 4월에 여행 갈 거예요. 맛집은 필요 없어요.",
                    lines=2,
                )
                submit_btn = gr.Button("실행")

            with gr.Column(scale=1):
                state_summary = gr.Markdown(
                    label="결과 요약",
                    value="실행 후 슬롯·서브 에이전트 결과가 여기 표시됩니다.",
                )

        def submit(user_input: str):
            chat_history, summary = run_agent(user_input)
            return chat_history, summary

        msg.submit(submit, inputs=[msg], outputs=[chatbot, state_summary])
        submit_btn.click(submit, inputs=[msg], outputs=[chatbot, state_summary])

        gr.Markdown("---\n*의도분류·대화에는 `.env`의 `OPENAI_MODEL`(기본 gpt-5-nano)이 사용됩니다.*")
    return demo


def main() -> None:
    """Gradio 앱 실행."""
    demo = build_ui()
    demo.launch()


if __name__ == "__main__":
    main()
