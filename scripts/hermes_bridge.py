#!/usr/bin/env python3
"""Run the Hermes-to-DevGodzilla bridge API."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.environ.get("HERMES_BRIDGE_HOST", "127.0.0.1")
    port = int(os.environ.get("HERMES_BRIDGE_PORT", "9025"))
    uvicorn.run("devgodzilla.hermes_bridge.app:app", host=host, port=port, reload=False, log_config=None)


if __name__ == "__main__":
    main()

