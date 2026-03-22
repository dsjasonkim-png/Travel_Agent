"""LangGraph `stream()`으로 노드 실행 과정을 로깅."""

from __future__ import annotations

import json
import logging
from typing import Any

from travel_agent.config import TRAVEL_AGENT_LOG_PREVIEW

logger = logging.getLogger("travel_agent.langgraph")


def _preview(obj: Any) -> str:
    try:
        s = json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        s = repr(obj)
    if len(s) > TRAVEL_AGENT_LOG_PREVIEW:
        return s[:TRAVEL_AGENT_LOG_PREVIEW] + "…"
    return s


def _format_namespace(ns: tuple) -> str:
    if not ns:
        return "supervisor"
    return " / ".join(str(p) for p in ns)


def _log_debug_event(ns_label: str, payload: dict[str, Any]) -> None:
    """stream_mode='debug' 이벤트 (task 시작·종료 등)."""
    kind = payload.get("type", "?")
    step = payload.get("step", "?")
    inner = payload.get("payload") or {}
    if kind == "task":
        name = inner.get("name", "?")
        logger.debug(
            "[LG debug] ns=%s step=%s task_start node=%s triggers=%s",
            ns_label,
            step,
            name,
            inner.get("triggers"),
        )
        logger.debug(
            "[LG debug] ns=%s task_input node=%s input=%s",
            ns_label,
            name,
            _preview(inner.get("input")),
        )
    elif kind == "task_result":
        name = inner.get("name", "?")
        err = inner.get("error")
        if err:
            logger.warning(
                "[LG debug] ns=%s step=%s task_result node=%s error=%s",
                ns_label,
                step,
                name,
                err,
            )
        else:
            logger.debug(
                "[LG debug] ns=%s step=%s task_result node=%s result=%s",
                ns_label,
                step,
                name,
                _preview(inner.get("result")),
            )
    else:
        logger.debug("[LG debug] ns=%s step=%s type=%s payload=%s", ns_label, step, kind, _preview(payload))


def _log_updates_event(ns_label: str, updates: dict[str, Any]) -> None:
    """stream_mode='updates': 노드별 반환(상태 델타)."""
    for node_name, update in updates.items():
        logger.info(
            "[LG update] ns=%s node=%s output=%s",
            ns_label,
            node_name,
            _preview(update),
        )


def _is_root_namespace(namespace: Any) -> bool:
    """LangGraph: 최상위 그래프는 namespace가 빈 튜플 () 입니다."""
    return namespace == () or namespace is None


def _consume_stream_event(
    event: Any,
    *,
    final_state_holder: list[dict[str, Any] | None],
) -> None:
    """단일 stream 이벤트를 로깅하고, 루트 그래프의 values만 final_state_holder에 반영.

    LangGraph `stream()` 산출 형식 (버전·옵션에 따라 다름):
    - v1 + `subgraphs=True` + `stream_mode`가 리스트: ``(namespace, mode, payload)``
    - v1 + `subgraphs=False` + 리스트: ``(mode, payload)``
    - v1 + 단일 모드 문자열: ``payload`` 만
    - v2: ``{"type", "ns", "data", ...}`` (values는 interrupts가 분리될 수 있음)

    `subgraphs=True`일 때 **서브그래프**의 ``values``가 마지막에 오면 전체 상태가 아닌
    부분 채널만 담긴 dict로 덮어써져 HITL ``__interrupt__`` 등이 사라질 수 있으므로,
    **namespace가 루트 ``()`` 인 values만** 최종 상태로 사용합니다.
    """
    # v2 dict 이벤트
    if isinstance(event, dict) and "type" in event:
        mode = event.get("type")
        namespace = event.get("ns")
        payload = event.get("data")
        ns_label = _format_namespace(namespace if isinstance(namespace, tuple) else ())

        if mode == "updates" and isinstance(payload, dict):
            _log_updates_event(ns_label, payload)
        elif mode == "debug" and isinstance(payload, dict):
            _log_debug_event(ns_label, payload)
        elif mode == "values" and isinstance(payload, dict):
            merged = dict(payload)
            ints = event.get("interrupts")
            if ints:
                merged["__interrupt__"] = ints
            logger.debug("[LG values] ns=%s state=%s", ns_label, _preview(merged))
            if _is_root_namespace(namespace):
                final_state_holder[0] = merged
        else:
            logger.debug("[LG stream] v2 이벤트 type=%s ns=%s", mode, ns_label)
        return

    # v1: (namespace, mode, payload)
    if isinstance(event, tuple) and len(event) == 3:
        namespace, mode, payload = event
        ns_label = _format_namespace(namespace)

        if mode == "updates":
            if isinstance(payload, dict):
                _log_updates_event(ns_label, payload)
            else:
                logger.info("[LG update] ns=%s raw=%s", ns_label, _preview(payload))
        elif mode == "debug":
            if isinstance(payload, dict):
                _log_debug_event(ns_label, payload)
            else:
                logger.debug("[LG debug] ns=%s raw=%s", ns_label, _preview(payload))
        elif mode == "values":
            if isinstance(payload, dict):
                logger.debug("[LG values] ns=%s state=%s", ns_label, _preview(payload))
                if _is_root_namespace(namespace):
                    final_state_holder[0] = payload
            else:
                logger.debug("[LG values] ns=%s raw=%s", ns_label, _preview(payload))
        return

    # v1: (mode, payload) — subgraphs=False + stream_mode 리스트
    if isinstance(event, tuple) and len(event) == 2:
        mode, payload = event
        ns_label = "supervisor"
        if mode == "updates":
            if isinstance(payload, dict):
                _log_updates_event(ns_label, payload)
            else:
                logger.info("[LG update] ns=%s raw=%s", ns_label, _preview(payload))
        elif mode == "debug":
            if isinstance(payload, dict):
                _log_debug_event(ns_label, payload)
            else:
                logger.debug("[LG debug] ns=%s raw=%s", ns_label, _preview(payload))
        elif mode == "values" and isinstance(payload, dict):
            logger.debug("[LG values] ns=%s state=%s", ns_label, _preview(payload))
            final_state_holder[0] = payload
        return

    # 단일 모드 등: 로그만
    logger.warning("[LG stream] 처리하지 않은 이벤트 형식: %s", type(event).__name__)


def run_with_stream_logging(
    graph: Any,
    input_state: Any,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """그래프를 stream으로 실행하며 updates·debug·values를 로깅하고, 최종 상태를 반환."""
    final_holder: list[dict[str, Any] | None] = [None]
    stream_modes = ["updates", "debug", "values"]
    kwargs: dict[str, Any] = {
        "stream_mode": stream_modes,
        "subgraphs": True,
    }
    if config is not None:
        kwargs["config"] = config

    for event in graph.stream(input_state, **kwargs):
        _consume_stream_event(event, final_state_holder=final_holder)

    final_state = final_holder[0]

    # 스트림에서 루트 values를 놓친 경우(구버전/예외 경로) 체크포인터 상태로 보강
    if final_state is None and config is not None:
        try:
            snap = graph.get_state(config)
            values = getattr(snap, "values", None) or {}
            if isinstance(values, dict) and values:
                final_state = dict(values)
                ints = getattr(snap, "interrupts", None)
                if ints:
                    final_state["__interrupt__"] = ints
                logger.warning(
                    "[LG stream] values 스트림이 없어 get_state()로 최종 상태를 채웠습니다."
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("[LG stream] get_state 보강 실패: %s", exc)

    if final_state is None:
        logger.error("[LG stream] values 이벤트가 없어 최종 상태를 알 수 없습니다.")
        return {}
    return final_state
