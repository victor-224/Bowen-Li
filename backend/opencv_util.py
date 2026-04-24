"""OpenCV logging helpers (suppress libpng stderr spam on corrupt reads)."""

from __future__ import annotations

import contextlib
from typing import Generator, Optional

_prev_log_level: Optional[int] = None


def _log_module():
    import cv2.utils.logging as m

    return m


def set_opencv_log_level(level: int) -> None:
    """Set global OpenCV log level (e.g. LOG_LEVEL_SILENT)."""
    m = _log_module()
    m.setLogLevel(level)


@contextlib.contextmanager
def opencv_imread_quiet() -> Generator[None, None, None]:
    """Temporarily silence OpenCV/libpng console output during imread."""
    m = _log_module()
    prev = m.getLogLevel()
    try:
        m.setLogLevel(m.LOG_LEVEL_SILENT)
        yield
    finally:
        m.setLogLevel(prev)


__all__ = ["opencv_imread_quiet", "set_opencv_log_level"]
