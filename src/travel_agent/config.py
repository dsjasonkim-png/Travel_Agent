"""환경 설정: .env 로드 및 OpenAI LLM(의도분류·대화용) 제공."""

import os

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def get_llm():
    """의도분류·대화에 사용할 OpenAI Chat 모델 인스턴스 반환 (GPT-5 nano 기본)."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY or None,  # None이면 환경변수 OPENAI_API_KEY 사용
        temperature=0.2,
    )
