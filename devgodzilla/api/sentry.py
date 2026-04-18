"""
DevGodzilla Sentry Error Tracking

Provides optional Sentry integration for error tracking and performance monitoring.
Completely disabled (no-op) when DEVGODZILLA_SENTRY_DSN is not set.
"""

import os
from typing import Optional

from devgodzilla.logging import get_logger

logger = get_logger(__name__)

# Track whether Sentry was successfully initialised.
_sentry_initialized = False


def _get_package_version() -> str:
    """Return the installed package version or a sensible default."""
    try:
        from importlib.metadata import version

        return version("devgodzilla")
    except Exception:
        return "0.1.0"


def init_sentry() -> bool:
    """
    Initialise the Sentry SDK for the FastAPI backend.

    Configuration is driven entirely by environment variables:

        DEVGODZILLA_SENTRY_DSN          – Sentry DSN (unset/empty = disabled)
        DEVGODZILLA_ENV                 – Environment tag (default: "development")
        DEVGODZILLA_SENTRY_TRACES_SAMPLE_RATE – Traces sample rate 0.0–1.0 (default: 0.2)
        DEVGODZILLA_SENTRY_PROFILES_SAMPLE_RATE – Profiles sample rate 0.0–1.0 (default: 0.1)

    Returns True if Sentry was enabled, False otherwise.
    """
    global _sentry_initialized  # noqa: PLW0603

    dsn: Optional[str] = os.environ.get("DEVGODZILLA_SENTRY_DSN") or None
    if not dsn:
        logger.info("sentry_disabled", extra={"reason": "DEVGODZILLA_SENTRY_DSN not set"})
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        logger.warning(
            "sentry_disabled",
            extra={"reason": "sentry-sdk[fastapi] not installed – pip install sentry-sdk[fastapi]"},
        )
        return False

    environment = os.environ.get("DEVGODZILLA_ENV", "development")
    release = _get_package_version()
    traces_sample_rate = float(
        os.environ.get("DEVGODZILLA_SENTRY_TRACES_SAMPLE_RATE", "0.2")
    )
    profiles_sample_rate = float(
        os.environ.get("DEVGODZILLA_SENTRY_PROFILES_SAMPLE_RATE", "0.1")
    )

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
        integrations=[
            StarletteIntegration(),
            FastApiIntegration(),
        ],
        # Don't send PII by default.
        send_default_pii=False,
    )

    _sentry_initialized = True
    logger.info(
        "sentry_enabled",
        extra={
            "environment": environment,
            "release": release,
            "traces_sample_rate": traces_sample_rate,
            "profiles_sample_rate": profiles_sample_rate,
        },
    )
    return True


def is_sentry_initialized() -> bool:
    """Return whether Sentry SDK has been initialised and is active."""
    return _sentry_initialized
