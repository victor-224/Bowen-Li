"""Stable local demo launcher for Industrial Digital Twin backend."""

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
