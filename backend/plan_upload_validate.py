"""Validate uploaded layout raster files before committing to runtime plan.png."""

from __future__ import annotations

from pathlib import Path

import cv2


def _is_png_magic(data: bytes) -> bool:
    return len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n"


def _is_jpeg_magic(data: bytes) -> bool:
    return len(data) >= 3 and data[:3] == b"\xff\xd8\xff"


def _is_pdf_magic(data: bytes) -> bool:
    return len(data) >= 5 and data[:5] == b"%PDF-"


def validate_layout_raster(path: Path) -> tuple[bool, str]:
    """
    Return (ok, reason). Uses PNG/JPEG magic bytes plus OpenCV decode as a second gate
    so corrupt files (wrong IHDR, truncated) are rejected before replacing runtime plan.
    """
    if not path.is_file():
        return False, "file_missing"
    try:
        raw = path.read_bytes()[:4096]
    except OSError as e:
        return False, f"read_error:{e}"

    if _is_pdf_magic(raw):
        return False, "file_is_pdf_not_image"

    suf = path.suffix.lower()
    if suf == ".png" and not _is_png_magic(raw):
        return False, "invalid_png_signature"
    if suf in {".jpg", ".jpeg"} and not _is_jpeg_magic(raw):
        return False, "invalid_jpeg_signature"

    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        return False, "opencv_decode_failed"

    return True, ""


__all__ = ["validate_layout_raster"]
