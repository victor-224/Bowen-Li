"""Phase 5: serializable payload for web / API consumers (no UI code)."""

from __future__ import annotations

from typing import Any, Dict


def web_ui(scene: Dict[str, Any]) -> Dict[str, Any]:
    """
    Web-layer data envelope (structure only; no HTML/JS).

    Returns a dict suitable for JSON encoding and consumption by HTTP handlers.
    """
    return {
        "scene": scene,
        "status": "ready",
        "render_mode": "three.js-ready",
    }
