"""Unified optional AI service: vision, copilot, reasoning. All delegate to ``call_lmstudio_model``.

Pipeline and OCR never depend on this module succeeding.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.config import get_ai_model_defaults, get_lm_studio_chat_url
from backend.llm.lmstudio_client import call_lmstudio_model


def _defaults() -> Dict[str, str]:
    return get_ai_model_defaults()


def call_vision_model(
    messages: List[Dict[str, Any]],
    *,
    model: Optional[str] = None,
    temperature: float = 0.2,
    timeout: int = 25,
    max_tokens: int = 512,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    m = (model or _defaults().get("vision") or "qwen2.5-vl-7b-instruct").strip()
    return call_lmstudio_model(
        m,
        messages,
        temperature,
        timeout,
        max_tokens,
        role="vision",
        base_url=base_url,
    )


def call_copilot_model(
    messages: List[Dict[str, Any]],
    *,
    model: Optional[str] = None,
    temperature: float = 0.3,
    timeout: int = 45,
    max_tokens: int = 1024,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    m = (model or _defaults().get("copilot") or "qwen3-8b-instruct").strip()
    return call_lmstudio_model(
        m,
        messages,
        temperature,
        timeout,
        max_tokens,
        role="copilot",
        base_url=base_url,
    )


def call_reasoning_model(
    messages: List[Dict[str, Any]],
    *,
    model: Optional[str] = None,
    temperature: float = 0.2,
    timeout: int = 45,
    max_tokens: int = 1024,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    m = (model or _defaults().get("reasoning") or "deepseek-r1-distill-qwen-8b").strip()
    return call_lmstudio_model(
        m,
        messages,
        temperature,
        timeout,
        max_tokens,
        role="reasoning",
        base_url=base_url,
    )


def ai_offline_envelope(error: str = "AI_OFFLINE") -> Dict[str, Any]:
    return {"success": False, "error": error, "fallback": True}


__all__ = [
    "call_vision_model",
    "call_copilot_model",
    "call_reasoning_model",
    "ai_offline_envelope",
    "get_lm_studio_chat_url",
]
