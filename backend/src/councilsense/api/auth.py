from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import base64
import hashlib
import hmac
import json
from typing import Annotated

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from councilsense.app.settings import Settings


UNAUTHORIZED_BODY = {
    "error": {
        "code": "unauthorized",
        "message": "Authentication required",
    }
}


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    email: str | None = None


class SessionValidationError(Exception):
    pass


class UnauthorizedError(Exception):
    pass


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _json_from_b64url(value: str) -> dict:
    try:
        raw_bytes = _b64url_decode(value)
        return json.loads(raw_bytes.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SessionValidationError("Malformed token payload") from exc


def _validate_signature(signing_input: str, signature: str, secret: str) -> None:
    digest = hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("utf-8")
    if not hmac.compare_digest(expected, signature):
        raise SessionValidationError("Invalid session signature")


def decode_session_token(token: str, secret: str) -> AuthenticatedUser:
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError as exc:
        raise SessionValidationError("Malformed session token") from exc

    _json_from_b64url(header_segment)
    payload = _json_from_b64url(payload_segment)
    _validate_signature(f"{header_segment}.{payload_segment}", signature_segment, secret)

    subject = payload.get("sub")
    expiry = payload.get("exp")
    email = payload.get("email")

    if not isinstance(subject, str) or not subject.strip():
        raise SessionValidationError("Session missing subject")
    if not isinstance(expiry, int):
        raise SessionValidationError("Session missing expiration")
    if email is not None and not isinstance(email, str):
        raise SessionValidationError("Session email claim is invalid")

    now = int(datetime.now(tz=UTC).timestamp())
    if expiry <= now:
        raise SessionValidationError("Session expired")

    return AuthenticatedUser(user_id=subject, email=email)


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self._settings = settings

    async def dispatch(self, request: Request, call_next):
        if self._settings.disable_auth_guard:
            request.state.auth_user = AuthenticatedUser(user_id=self._settings.local_dev_auth_user_id)
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            request.state.auth_user = None
            return await call_next(request)

        token = auth_header.removeprefix("Bearer ").strip()
        try:
            request.state.auth_user = decode_session_token(token, self._settings.auth_session_secret)
        except SessionValidationError:
            return JSONResponse(status_code=401, content=UNAUTHORIZED_BODY)

        return await call_next(request)


def _extract_user(request: Request) -> AuthenticatedUser:
    user = getattr(request.state, "auth_user", None)
    if user is None:
        raise UnauthorizedError
    return user


def get_current_user(user: Annotated[AuthenticatedUser, Depends(_extract_user)]) -> AuthenticatedUser:
    return user
