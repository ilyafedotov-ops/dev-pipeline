from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BridgeConfig:
    devgodzilla_base_url: str
    devgodzilla_api_token: str | None
    hermes_bridge_token: str | None
    timeout_seconds: float


def load_bridge_config() -> BridgeConfig:
    base_url = os.environ.get("HERMES_DEVGODZILLA_BASE_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")
    return BridgeConfig(
        devgodzilla_base_url=base_url,
        devgodzilla_api_token=os.environ.get("HERMES_DEVGODZILLA_API_TOKEN") or os.environ.get("DEVGODZILLA_API_TOKEN"),
        hermes_bridge_token=os.environ.get("HERMES_BRIDGE_TOKEN"),
        timeout_seconds=float(os.environ.get("HERMES_DEVGODZILLA_TIMEOUT_SECONDS", "60")),
    )

