"""Run the local HTML demo server."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    port = int(os.getenv("DEMO_UI_PORT", "8008"))
    uvicorn.run("demo_ui.app:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
