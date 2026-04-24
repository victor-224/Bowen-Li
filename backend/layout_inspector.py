"""Runtime layout file health check for UI (Upload File Inspector)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import cv2

from backend.plan_upload_validate import validate_layout_raster


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_runtime_plan_path() -> Path:
    return _repo_root() / "data" / "runtime" / "plan.png"


def _magic_label(data: bytes) -> str:
    if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return "PNG"
    if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
        return "JPEG"
    if len(data) >= 5 and data[:5] == b"%PDF-":
        return "PDF"
    return "unknown"


def inspect_runtime_layout(plan_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Inspect committed runtime layout (typically data/runtime/plan.png).

    Fields are UI-oriented; ``used_for_spatial`` means the raster is decodable
    and passes the same validation gate used on upload (eligible as layout input).
    """
    p = Path(plan_path) if plan_path is not None else default_runtime_plan_path()
    out: Dict[str, Any] = {
        "layout_file": str(p),
        "exists": False,
        "file_type": "—",
        "magic_detected": "unknown",
        "resolution": "—",
        "width": None,
        "height": None,
        "decode_ok": False,
        "readable": False,
        "validation_ok": False,
        "used_for_spatial": False,
        "validation_reason": "",
        "bytes": 0,
    }

    if not p.is_file():
        return out

    out["exists"] = True
    try:
        st = p.stat()
        out["bytes"] = int(st.st_size)
    except OSError:
        out["bytes"] = 0

    out["readable"] = out["bytes"] > 0
    suf = p.suffix.lower().lstrip(".") or "bin"
    out["file_type"] = suf.upper() if suf != "bin" else "unknown"

    try:
        head = p.read_bytes()[:4096]
    except OSError:
        head = b""

    out["magic_detected"] = _magic_label(head)

    ok_val, reason = validate_layout_raster(p)
    out["validation_ok"] = bool(ok_val)
    out["validation_reason"] = reason or ""

    img = cv2.imread(str(p), cv2.IMREAD_COLOR)
    if img is not None:
        h, w = img.shape[:2]
        out["decode_ok"] = True
        out["width"] = int(w)
        out["height"] = int(h)
        out["resolution"] = f"{w}×{h}"
    else:
        out["decode_ok"] = False
        out["resolution"] = "—"

    out["used_for_spatial"] = bool(out["decode_ok"] and out["validation_ok"])

    return out


__all__ = ["inspect_runtime_layout", "default_runtime_plan_path"]
