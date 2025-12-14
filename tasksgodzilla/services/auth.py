import secrets
import time
from dataclasses import dataclass
from typing import Any, Optional

from tasksgodzilla.auth.jwt import JwtError, decode_hs256, encode_hs256
from tasksgodzilla.auth.passwords import verify_pbkdf2_sha256
from tasksgodzilla.config import Config
from tasksgodzilla.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class AuthPrincipal:
    subject: str
    username: str


class AuthService:
    def __init__(self, *, config: Config):
        self._config = config

    def get_mode(self) -> str:
        if self._config.oidc_enabled:
            return "oidc"
        if self._config.jwt_enabled:
            return "jwt"
        if self._config.api_token:
            return "token"
        return "open"

    def verify_admin_password(self, username: str, password: str) -> bool:
        if not (username and password):
            return False
        if not self._config.admin_username:
            return False
        if username != self._config.admin_username:
            return False

        if self._config.admin_password_hash:
            return verify_pbkdf2_sha256(self._config.admin_password_hash, password)

        # Dev-only fallback: plain env password.
        if self._config.admin_password is None:
            return False
        return secrets.compare_digest(self._config.admin_password, password)

    def create_access_token(self, principal: AuthPrincipal) -> str:
        if not self._config.jwt_secret:
            raise ValueError("JWT secret not configured")
        now = int(time.time())
        ttl = int(self._config.jwt_access_ttl_seconds or 0)
        if ttl <= 0:
            ttl = 60 * 15
        payload: dict[str, Any] = {
            "iss": self._config.jwt_issuer or "tasksgodzilla",
            "sub": principal.subject,
            "username": principal.username,
            "typ": "access",
            "iat": now,
            "exp": now + ttl,
        }
        return encode_hs256(payload, self._config.jwt_secret)

    def create_refresh_token(self, principal: AuthPrincipal, *, jti: str) -> str:
        if not self._config.jwt_secret:
            raise ValueError("JWT secret not configured")
        now = int(time.time())
        ttl = int(self._config.jwt_refresh_ttl_seconds or 0)
        if ttl <= 0:
            ttl = 60 * 60 * 24 * 14
        payload: dict[str, Any] = {
            "iss": self._config.jwt_issuer or "tasksgodzilla",
            "sub": principal.subject,
            "username": principal.username,
            "typ": "refresh",
            "jti": jti,
            "iat": now,
            "exp": now + ttl,
        }
        return encode_hs256(payload, self._config.jwt_secret)

    def verify_access_token(self, token: str) -> Optional[AuthPrincipal]:
        if not (self._config.jwt_enabled and self._config.jwt_secret):
            return None
        try:
            payload = decode_hs256(token, self._config.jwt_secret)
        except JwtError:
            return None
        if payload.get("typ") != "access":
            return None
        username = payload.get("username")
        sub = payload.get("sub")
        if not username or not sub:
            return None
        return AuthPrincipal(subject=str(sub), username=str(username))

    def verify_refresh_token(self, token: str) -> tuple[Optional[AuthPrincipal], Optional[str]]:
        if not (self._config.jwt_enabled and self._config.jwt_secret):
            return None, None
        try:
            payload = decode_hs256(token, self._config.jwt_secret)
        except JwtError:
            return None, None
        if payload.get("typ") != "refresh":
            return None, None
        username = payload.get("username")
        sub = payload.get("sub")
        jti = payload.get("jti")
        if not username or not sub or not jti:
            return None, None
        return AuthPrincipal(subject=str(sub), username=str(username)), str(jti)

