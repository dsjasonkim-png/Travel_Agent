"""환경 설정: .env 로드, OpenAI LLM, 로깅 옵션."""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
SERPAPI_API_KEY: str = os.getenv("SERPAPI_API_KEY", "")

# LangGraph 스트리밍 로그 (.env에서 설정)
TRAVEL_AGENT_LOG_LEVEL: str = os.getenv("TRAVEL_AGENT_LOG_LEVEL", "INFO")
TRAVEL_AGENT_LOG_PREVIEW: int = int(os.getenv("TRAVEL_AGENT_LOG_PREVIEW", "800"))
# `graph_stream`의 [LG debug]/[LG values]는 DEBUG. 루트만 INFO면 터미널에 안 보이므로
# 이 로거만 기본 DEBUG (다른 라이브러리는 루트 INFO로 조용히 유지).
TRAVEL_AGENT_LANGGRAPH_LOG_LEVEL: str = os.getenv(
    "TRAVEL_AGENT_LANGGRAPH_LOG_LEVEL", "DEBUG"
)


def configure_logging() -> None:
    """루트 로거 포맷·레벨 설정. CLI·Gradio 진입 시 한 번 호출."""
    level_name = TRAVEL_AGENT_LOG_LEVEL.upper()
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        force=True,
    )

    lg_name = "travel_agent.langgraph"
    lg_level_name = TRAVEL_AGENT_LANGGRAPH_LOG_LEVEL.strip().upper() or "DEBUG"
    lg_level = getattr(logging, lg_level_name, None)
    if not isinstance(lg_level, int):
        lg_level = logging.DEBUG
    langgraph_logger = logging.getLogger(lg_name)
    langgraph_logger.setLevel(lg_level)
    langgraph_logger.propagate = True


def get_llm():
    """의도분류·대화에 사용할 OpenAI Chat 모델 인스턴스 반환."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY or None,  # None이면 환경변수 OPENAI_API_KEY 사용
        temperature=0.2,
    )
