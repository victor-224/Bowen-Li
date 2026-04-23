"""LM Studio OpenAI-compatible chat completions adapter.

Safe infrastructure-only layer. Does not modify pipeline, scene, OCR,
state machine, or API routes. Never raises outward.
"""

from __future__ import annotations

import errno
import json
import logging
import socket
from typing import Any, Dict, List, Optional, Tuple
from urllib import error as urlerror
from urllib import request as urlrequest


LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"

MODELS: List[str] = [
    "qwen2.5-vl-7b-instruct",
    "internvl3.5-8b",
    "deepseek-r1-distill-qwen-8b",
    "qwen3-8b-instruct",
]

logger = logging.getLogger("industrial_digital_twin.llm.lmstudio")


def _is_offline(exc: BaseException) -> bool:
    """Return True when the exception suggests LM Studio is not reachable at all."""
    if isinstance(exc, urlerror.HTTPError):
        return False
    if isinstance(exc, urlerror.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, ConnectionRefusedError):
            return True
        if isinstance(reason, socket.gaierror):
            return True
        if isinstance(reason, OSError):
            err_no = getattr(reason, "errno", None)
            if err_no in {errno.ECONNREFUSED, errno.EHOSTUNREACH, errno.ENETUNREACH}:
                return True
        if isinstance(reason, str):
            lowered = reason.lower()
            if (
                "refused" in lowered
                or "unreachable" in lowered
                or "name or service not known" in lowered
                or "no address associated" in lowered
                or "nodename nor servname" in lowered
            ):
                return True
    if isinstance(exc, ConnectionRefusedError):
        return True
    return False


def _safe_extract_content(raw: Dict[str, Any]) -> str:
    if not isinstance(raw, dict):
        return ""
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0] if isinstance(choices[0], dict) else None
    if first is None:
        return ""
    message = first.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
    text = first.get("text")
    if isinstance(text, str):
        return text
    return ""


def _post_chat(
    model: str,
    messages: List[Dict[str, Any]],
    temperature: float,
    max_tokens: int,
    timeout: int,
) -> Dict[str, Any]:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(
        LM_STUDIO_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urlrequest.urlopen(req, timeout=timeout) as resp:
        raw_bytes = resp.read()
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except json.JSONDecodeError:
        raise
    if not isinstance(data, dict):
        raise ValueError("LM Studio response was not a JSON object")
    return data


def _attempt_with_retry(
    model: str,
    messages: List[Dict[str, Any]],
    temperature: float,
    max_tokens: int,
    timeout: int,
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[BaseException]]:
    """Try once, retry once. Returns (ok, raw, last_exc)."""
    last_exc: Optional[BaseException] = None
    for attempt in (1, 2):
        try:
            raw = _post_chat(model, messages, temperature, max_tokens, timeout)
            return True, raw, None
        except urlerror.HTTPError as e:
            last_exc = e
            logger.warning("LM Studio HTTPError model=%s attempt=%d status=%s", model, attempt, getattr(e, "code", "?"))
            if getattr(e, "code", 500) and int(getattr(e, "code", 500)) < 500:
                break
        except (urlerror.URLError, TimeoutError, socket.timeout) as e:
            last_exc = e
            logger.warning("LM Studio URLError model=%s attempt=%d reason=%r", model, attempt, getattr(e, "reason", e))
            if _is_offline(e):
                return False, None, e
        except (json.JSONDecodeError, ValueError) as e:
            last_exc = e
            logger.warning("LM Studio bad payload model=%s attempt=%d err=%r", model, attempt, e)
        except Exception as e:  # noqa: BLE001 - never raise out
            last_exc = e
            logger.warning("LM Studio unexpected error model=%s attempt=%d err=%r", model, attempt, e)
    return False, None, last_exc


def call_lmstudio_model(
    model: str,
    messages: List[Dict[str, Any]],
    temperature: float = 0.2,
    timeout: int = 25,
    max_tokens: int = 512,
) -> Dict[str, Any]:
    """Call LM Studio with retry + fallback. Never raises outward.

    Returns a strict envelope:
      success: {"model", "content", "raw", "success": True}
      failure: {"success": False, "error": "LM_STUDIO_OFFLINE"}
               or {"success": False, "error": "LM_STUDIO_ALL_MODELS_FAILED",
                   "model": <last>, "raw": {}}
    """
    if not isinstance(messages, list):
        return {"success": False, "error": "LM_STUDIO_BAD_REQUEST"}

    # 1) requested model with 1 retry
    logger.info("LM Studio attempt model=%s", model)
    ok, raw, err = _attempt_with_retry(model, messages, temperature, max_tokens, timeout)
    if ok and raw is not None:
        return {
            "model": model,
            "content": _safe_extract_content(raw),
            "raw": raw,
            "success": True,
        }
    if err is not None and _is_offline(err):
        logger.warning("LM Studio offline on first contact model=%s", model)
        return {"success": False, "error": "LM_STUDIO_OFFLINE"}

    # 2) full fallback list skipping the already-tried requested model
    last_tried = model
    last_err = err
    for candidate in MODELS:
        if candidate == model:
            continue
        last_tried = candidate
        logger.info("LM Studio fallback attempt model=%s", candidate)
        ok, raw, err = _attempt_with_retry(candidate, messages, temperature, max_tokens, timeout)
        if ok and raw is not None:
            return {
                "model": candidate,
                "content": _safe_extract_content(raw),
                "raw": raw,
                "success": True,
            }
        last_err = err
        if err is not None and _is_offline(err):
            logger.warning("LM Studio offline during fallback model=%s", candidate)
            return {"success": False, "error": "LM_STUDIO_OFFLINE"}

    logger.warning("LM Studio all models failed last=%s last_err=%r", last_tried, last_err)
    return {
        "success": False,
        "error": "LM_STUDIO_ALL_MODELS_FAILED",
        "model": last_tried,
        "raw": {},
    }


__all__ = ["LM_STUDIO_URL", "MODELS", "call_lmstudio_model"]
