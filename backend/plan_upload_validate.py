"""Validate uploaded layout raster files before committing to runtime plan.png."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import cv2

from backend.opencv_util import opencv_imread_quiet


def _is_png_magic(data: bytes) -> bool:
    return len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n"


def _is_jpeg_magic(data: bytes) -> bool:
    return len(data) >= 3 and data[:3] == b"\xff\xd8\xff"


def _is_pdf_magic(data: bytes) -> bool:
    return len(data) >= 5 and data[:5] == b"%PDF-"


def validate_layout_raster(path: Path) -> tuple[bool, str, Optional[Tuple[int, int]]]:
    """
    Return (ok, reason, size_wh).

    ``size_wh`` is ``(width, height)`` in pixels when decode succeeds; otherwise ``None``.
    Uses PNG/JPEG magic bytes before ``imread`` so broken PNGs do not spam libpng on stderr.
    """
    if not path.is_file():
        return False, "file_missing", None
    try:
        raw = path.read_bytes()[:4096]
    except OSError as e:
        return False, f"read_error:{e}", None

    if _is_pdf_magic(raw):
        return False, "file_is_pdf_not_image", None

    suf = path.suffix.lower()
    if suf == ".png" and not _is_png_magic(raw):
        return False, "invalid_png_signature", None
    if suf in {".jpg", ".jpeg"} and not _is_jpeg_magic(raw):
        return False, "invalid_jpeg_signature", None

    with opencv_imread_quiet():
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        return False, "opencv_decode_failed", None

    h, w = img.shape[:2]
    return True, "", (int(w), int(h))


__all__ = ["validate_layout_raster"]
