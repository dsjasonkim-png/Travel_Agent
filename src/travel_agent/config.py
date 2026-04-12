"""환경 설정: .env 로드, OpenAI LLM, 로깅 옵션."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env")

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "")
FLIGHT_SERPAPI_API_KEY: str = os.getenv(
    "flight_serpapi_api_key",
    os.getenv("FLIGHT_SERPAPI_API_KEY", ""),
)

# LangGraph 스트리밍 로그 (.env에서 설정)
TRAVEL_AGENT_LOG_LEVEL: str = os.getenv("TRAVEL_AGENT_LOG_LEVEL", "WARNING")
TRAVEL_AGENT_LOG_PREVIEW: int = int(os.getenv("TRAVEL_AGENT_LOG_PREVIEW", "240"))
TRAVEL_AGENT_LANGGRAPH_LOG_LEVEL: str = os.getenv(
    "TRAVEL_AGENT_LANGGRAPH_LOG_LEVEL", "INFO"
)


def _parse_log_level(level_name: str, default: int) -> int:
    level = getattr(logging, level_name.upper(), None)
    return level if isinstance(level, int) else default


def configure_logging() -> None:
    """기본 로그는 숨기고 LangGraph stream 로그만 보이도록 설정."""
    root_level = _parse_log_level(TRAVEL_AGENT_LOG_LEVEL, logging.WARNING)
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
    root_logger.handlers.clear()
    root_logger.setLevel(root_level)
    root_logger.addHandler(logging.NullHandler())

    lg_name = "travel_agent.langgraph"
    lg_level = _parse_log_level(TRAVEL_AGENT_LANGGRAPH_LOG_LEVEL.strip() or "INFO", logging.INFO)
    langgraph_logger = logging.getLogger(lg_name)
    for handler in list(langgraph_logger.handlers):
        langgraph_logger.removeHandler(handler)
    handler = logging.StreamHandler()
    handler.setLevel(lg_level)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S")
    )
    langgraph_logger.addHandler(handler)
    langgraph_logger.setLevel(lg_level)
    langgraph_logger.propagate = False


def get_llm():
    """의도분류·대화에 사용할 OpenAI Chat 모델 인스턴스 반환."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY or None,  # None이면 환경변수 OPENAI_API_KEY 사용
        temperature=0.2,
    )
