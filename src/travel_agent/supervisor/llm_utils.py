"""슈퍼바이저 노드용 LLM 호출·JSON 파싱 보조."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage

from travel_agent.config import get_llm


def invoke_text(prompt: str) -> str:
    llm = get_llm()
    out = llm.invoke([HumanMessage(content=prompt)])
    return (out.content if hasattr(out, "content") else str(out)).strip()


def parse_json_object(text: str) -> dict[str, Any] | None:
    """LLM 응답에서 첫 JSON 객체 추출."""
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text) or re.search(r"\{[\s\S]*\}", text)
    if not json_match:
        return None
    raw = json_match.group(1) if "```" in text else json_match.group(0)
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None
