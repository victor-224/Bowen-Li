"""Stable local demo launcher for Industrial Digital Twin backend."""

try:
    import cv2.utils.logging as _cv2_log

    _cv2_log.setLogLevel(_cv2_log.LOG_LEVEL_SILENT)
except Exception:  # noqa: BLE001
    pass

from backend.api import app


def main() -> None:
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=True,
    )


if __name__ == "__main__":
    main()
