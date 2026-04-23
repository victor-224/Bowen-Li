"""Unified Vision model interface (LM Studio multimodal, OpenAI-style messages).

Isolated: not used by the pipeline, API, or OCR. Never raises to callers.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import socket
from typing import Any, Dict, List, Optional, Tuple
from urllib import error as urlerror
from urllib import request as urlrequest

# Required: shared LM Studio adapter (this module also POSTs one model at a time
# to enforce vision-only fallbacks, matching ``call_lmstudio_model``'s local URL).
from backend.llm.lmstudio_client import call_lmstudio_model

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"

logger = logging.getLogger("industrial_digital_twin.vision")

# After the primary, try in this order; skip any model name already used.
_VISION_FALLBACK: List[str] = [
    "qwen2.5-vl-7b-instruct",
    "internvl3.5-8b",
]

__all__ = ["image_to_base64", "run_vision_model", "call_lmstudio_model"]


def _post_chat(
    model: str,
    messages: List[Dict[str, Any]],
    temperature: float,
    max_tokens: int,
    timeout: int,
) -> Dict[str, Any]:
    """POST to LM Studio. Raises on I/O, bad JSON, or non-object result."""
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
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urlrequest.urlopen(req, timeout=timeout) as resp:
        raw_bytes = resp.read()
    data = json.loads(raw_bytes.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("LM Studio response was not a JSON object")
    return data


def _is_offline(exc: BaseException) -> bool:
    if isinstance(exc, urlerror.HTTPError):
        return False
    if isinstance(exc, urlerror.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(
            reason,
            (ConnectionRefusedError, OSError, socket.gaierror, socket.timeout),
        ):
            return True
    if isinstance(exc, (ConnectionRefusedError, OSError, socket.gaierror)):
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
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return str(message.get("content", ""))
    text = first.get("text")
    if isinstance(text, str):
        return text
    return ""


def _attempt_with_retry(
    model: str,
    messages: List[Dict[str, Any]],
    temperature: float,
    max_tokens: int,
    timeout: int,
) -> Tuple[bool, Optional[Dict[str, Any]], bool]:
    """Try ``model`` once, retry once. Returns (ok, raw, offline_saw)."""
    last_offline = False
    for attempt in (1, 2):
        try:
            raw = _post_chat(
                model, messages, temperature, max_tokens, timeout
            )
            return True, raw, last_offline
        except urlerror.HTTPError as e:
            last_offline = False
            code = int(getattr(e, "code", 500) or 500)
            logger.error(
                "vision LM HTTPError model=%s attempt=%d status=%s",
                model,
                attempt,
                code,
            )
            if 400 <= code < 500:
                break
        except (urlerror.URLError, TimeoutError, socket.timeout) as e:
            if _is_offline(e):
                last_offline = True
            logger.error("vision LM URLError model=%s attempt=%d err=%r", model, attempt, e)
        except (json.JSONDecodeError, ValueError) as e:
            last_offline = False
            logger.error("vision LM bad response model=%s attempt=%d err=%r", model, attempt, e)
        except Exception as e:  # noqa: BLE001
            last_offline = False
            logger.error("vision LM unexpected model=%s attempt=%d err=%r", model, attempt, e)
    return False, None, last_offline


def _user_message(prompt: str, data_url: str) -> List[Dict[str, Any]]:
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": data_url},
                },
            ],
        }
    ]


def _mime_for_path(path: str) -> str:
    low = str(path).lower()
    if low.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if low.endswith(".png"):
        return "image/png"
    return "image/png"


def image_to_base64(path: str) -> Optional[str]:
    """Read a file and return its base64 payload, or None if not usable."""
    if not path or not isinstance(path, str):
        logger.error("image_to_base64: invalid path %r", path)
        return None
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        logger.error("image_to_base64: read error for %s: %s", path, e)
        return None
    if not data:
        logger.error("image_to_base64: empty file %s", path)
        return None
    try:
        return base64.b64encode(data).decode("ascii")
    except (ValueError, TypeError) as e:
        logger.error("image_to_base64: encode error for %s: %s", path, e)
        return None


def _ok(
    used_model: str,
    objects: List[Any],
    relations: List[Any],
    confidence: float,
    raw_text: str,
) -> Dict[str, Any]:
    return {
        "success": True,
        "objects": list(objects),
        "relations": list(relations),
        "metadata": {
            "model": used_model,
            "confidence": float(confidence),
            "raw_text": raw_text,
        },
    }


def _not_found() -> Dict[str, Any]:
    return {
        "success": False,
        "error": "IMAGE_NOT_FOUND",
        "objects": [],
        "relations": [],
        "metadata": {},
    }


def _all_failed(offline: bool) -> Dict[str, Any]:
    return {
        "success": False,
        "error": "LM_STUDIO_OFFLINE" if offline else "VISION_ALL_FAILED",
        "objects": [],
        "relations": [],
        "metadata": {
            "model": "",
            "confidence": 0.0,
            "raw_text": "",
        },
    }


def _parse_model_text(text: str, used_model: str) -> Dict[str, Any]:
    """Try JSON; keep ``raw_text`` for debugging; never raise."""
    t = (text or "").strip()
    if not t:
        return _ok(used_model, [], [], 0.0, "")

    data: Any
    try:
        data = json.loads(t)
    except json.JSONDecodeError as e:
        logger.error("vision: invalid JSON, preserving raw text: %s", e)
        return _ok(used_model, [], [], 0.0, t)

    if isinstance(data, list):
        return _ok(used_model, list(data), [], 0.0, t)

    if not isinstance(data, dict):
        return _ok(used_model, [], [], 0.0, t)

    objs: List[Any] = []
    rels: List[Any] = []
    if isinstance(data.get("objects"), list):
        objs = list(data["objects"])
    if isinstance(data.get("relations"), list):
        rels = list(data["relations"])

    conf = 0.0
    c = data.get("confidence")
    if c is not None and isinstance(c, (int, float)) and not isinstance(c, bool):
        conf = float(c)
    else:
        meta = data.get("metadata")
        if isinstance(meta, dict):
            mc = meta.get("confidence")
            if isinstance(mc, (int, float)) and not isinstance(mc, bool):
                conf = float(mc)

    if "objects" in data or "relations" in data or "confidence" in data:
        return _ok(used_model, objs, rels, conf, t)
    return _ok(used_model, [], [], 0.0, t)


def _model_sequence(requested: str) -> List[str]:
    m0 = str(requested) if requested else "qwen2.5-vl-7b-instruct"
    out: List[str] = []
    for name in (m0, *_VISION_FALLBACK):
        if name not in out:
            out.append(name)
    return out


def run_vision_model(
    image_path: str,
    prompt: str,
    model: str = "qwen2.5-vl-7b-instruct",
    *,
    temperature: float = 0.2,
    timeout: int = 25,
    max_tokens: int = 512,
) -> Dict[str, Any]:
    """
    Call a local VLM (multimodal) via LM Studio. Returns a strict result dict; never
    raises.

    Tries, in order: ``model``, then :data:`_VISION_FALLBACK` entries, each name
    at most once.
    """
    # Expose the adapter in this module; vision uses :func:`_post_chat` so
    # fallback order is primary → qwen2.5-vl-7b → internvl3.5-8b (see module docstring).
    _ = call_lmstudio_model

    b64 = image_to_base64(image_path)
    if b64 is None:
        p = str(image_path) if image_path is not None else ""
        if not p or not os.path.isfile(p):
            logger.error("run_vision_model: image not found %r", image_path)
            return _not_found()
        logger.error("run_vision_model: image unreadable or malformed %r", image_path)
        return {
            "success": False,
            "error": "IMAGE_MALFORMED",
            "objects": [],
            "relations": [],
            "metadata": {
                "model": "",
                "confidence": 0.0,
                "raw_text": "",
            },
        }

    data_url = f"data:{_mime_for_path(str(image_path))};base64,{b64}"
    messages = _user_message(str(prompt or ""), data_url)

    seq = _model_sequence(model)
    any_offline = False
    for idx, m in enumerate(seq):
        if idx == 0:
            logger.info("vision: model attempt model=%s", m)
        else:
            logger.warning("vision: fallback activation model=%s", m)
        ok, raw, offline = _attempt_with_retry(
            m, messages, temperature, max_tokens, timeout
        )
        if offline:
            any_offline = True
        if ok and raw is not None:
            text = _safe_extract_content(raw)
            return _parse_model_text(text, m)

    return _all_failed(any_offline)


if __name__ == "__main__":
    import importlib
    import os as _os
    import sys
    import tempfile
    from unittest.mock import patch

    n_fail = 0
    _m = importlib.import_module("backend.models.vision.vl_interface")
    tdir = tempfile.mkdtemp()
    good = _os.path.join(tdir, "a.png")
    with open(good, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + b"\0" * 8)

    r1 = _m.run_vision_model(
        _os.path.join(tdir, "nope.png"), "x", model="qwen2.5-vl-7b-instruct"
    )
    if r1.get("error") != "IMAGE_NOT_FOUND" or r1.get("metadata") != {}:
        print("FAIL D", r1)
        n_fail += 1
    else:
        print("OK D IMAGE_NOT_FOUND")

    with patch.object(
        _m,
        "_attempt_with_retry",
        return_value=(
            True,
            {"choices": [{"message": {"content": '{"objects":[],"relations":[]}'}}]},
            False,
        ),
    ):
        r2 = _m.run_vision_model(good, "p", model="qwen2.5-vl-7b-instruct")
        if not r2.get("success") or (r2.get("metadata") or {}).get("model") != "qwen2.5-vl-7b-instruct":
            print("FAIL A", r2)
            n_fail += 1
        else:
            print("OK A success")

    _calls: List[str] = []

    def _side_b(model, messages, t, mxt, to):
        _calls.append(model)
        if model == "qwen2.5-vl-7b-instruct":
            return (False, None, False)
        if model == "internvl3.5-8b":
            return (
                True,
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"objects":[1],"relations":[]}'
                            }
                        }
                    ]
                },
                False,
            )
        return (False, None, False)

    with patch.object(_m, "_attempt_with_retry", side_effect=_side_b):
        r3 = _m.run_vision_model(good, "p", model="qwen2.5-vl-7b-instruct")
        if (r3.get("metadata") or {}).get("model") != "internvl3.5-8b":
            print("FAIL B", r3, _calls)
            n_fail += 1
        else:
            print("OK B internvl after qwen fail")

    with patch.object(_m, "_attempt_with_retry", return_value=(False, None, True)):
        r4 = _m.run_vision_model(good, "p")
        if r4.get("error") != "LM_STUDIO_OFFLINE":
            print("FAIL C", r4)
            n_fail += 1
        else:
            print("OK C offline")

    with patch.object(
        _m,
        "_attempt_with_retry",
        return_value=(
            True,
            {
                "choices": [
                    {"message": {"content": "this is { not } valid json"}}
                ]
            },
            False,
        ),
    ):
        r5 = _m.run_vision_model(good, "p", model="internvl3.5-8b")
        rt = (r5.get("metadata") or {}).get("raw_text", "")
        if (not r5.get("success")) or "not" not in rt:
            print("FAIL E", r5)
            n_fail += 1
        else:
            print("OK E raw preserved")

    sys.exit(1 if n_fail else 0)
