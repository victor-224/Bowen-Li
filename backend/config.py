"""Central configuration: env-first, optional runtime JSON override in data/runtime."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

_REPO_ROOT = Path(__file__).resolve().parent.parent
AI_RUNTIME_CONFIG_FILE = _REPO_ROOT / "data" / "runtime" / "ai_config.json"

# LM Studio OpenAI-compatible chat completions URL (never hardcode host in callers).
DEFAULT_LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"


def _env_str(key: str, default: str = "") -> str:
    v = os.environ.get(key)
    if v is None or not str(v).strip():
        return default
    return str(v).strip()


def lm_studio_url_from_env() -> str:
    """Base URL from environment only (no runtime file)."""
    return _env_str("LM_STUDIO_URL", DEFAULT_LM_STUDIO_URL)


def _runtime_ai_json() -> Dict[str, Any]:
    p = AI_RUNTIME_CONFIG_FILE
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def get_lm_studio_chat_url() -> str:
    """Effective chat completions URL: runtime file overrides env; env overrides code default."""
    rt = _runtime_ai_json()
    url = (rt.get("lm_studio_url") or "").strip()
    if url:
        return url
    return lm_studio_url_from_env()


def get_ai_model_defaults() -> Dict[str, str]:
    """Default model IDs per role: runtime JSON overrides env; env overrides code default."""
    rt = _runtime_ai_json()
    out = {
        "vision": _env_str("AI_VISION_MODEL", "qwen2.5-vl-7b-instruct"),
        "copilot": _env_str("AI_COPILOT_MODEL", "qwen3-8b-instruct"),
        "reasoning": _env_str("AI_REASONING_MODEL", "deepseek-r1-distill-qwen-8b"),
    }
    for role, key in (("vision", "model_vision"), ("copilot", "model_copilot"), ("reasoning", "model_reasoning")):
        v = (rt.get(key) or "").strip()
        if v:
            out[role] = v
    return out


# Same order as backend.llm.lmstudio_client.MODELS (kept here to avoid import cycles).
_MODEL_FALLBACK_ORDER = [
    "qwen2.5-vl-7b-instruct",
    "internvl3.5-8b",
    "deepseek-r1-distill-qwen-8b",
    "qwen3-8b-instruct",
]


def get_models_for_role(role: str) -> list[str]:
    """Ordered candidates for a role (primary + shared fallback list)."""
    defaults = get_ai_model_defaults()
    primary = (defaults.get(role) or defaults.get("copilot") or "qwen3-8b-instruct").strip()
    out: list[str] = []
    if primary:
        out.append(primary)
    for m in _MODEL_FALLBACK_ORDER:
        if m not in out:
            out.append(m)
    return out


__all__ = [
    "AI_RUNTIME_CONFIG_FILE",
    "DEFAULT_LM_STUDIO_URL",
    "lm_studio_url_from_env",
    "get_lm_studio_chat_url",
    "get_ai_model_defaults",
    "get_models_for_role",
]
