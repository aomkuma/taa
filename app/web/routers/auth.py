"""``/api/v1/auth``: login with password + TOTP, session info, logout, step-up and TOTP re-enrollment.

Error codes the PWA relies on:

- ``invalid_credentials`` (401): any login failure
- ``too_many_attempts`` (429, with Retry-After)
- ``unauthenticated`` (401): no live session
- ``csrf_failed`` / ``origin_not_allowed`` / ``step_up_required`` (403)
- ``invalid_code`` / ``invalid_password`` (400; not 401, so they never look like an expired session)
"""

from __future__ import annotations

import base64
from typing import Any

import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.security.passwords import MAX_LENGTH
from app.web.auth import ABSOLUTE_TIMEOUT, IDLE_TIMEOUT, AuthFailure, AuthService, AuthSession
from app.web.deps import (
    Context,
    CsrfSession,
    CurrentSession,
    StepUpSession,
    check_origin,
    client_ip,
    session_cookie_name,
)
from app.web.errors import ApiProblem

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=MAX_LENGTH)
    code: str = Field(min_length=6, max_length=8)


class CodeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=6, max_length=8)


class PasswordBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=MAX_LENGTH)


def _problem(exc: AuthFailure) -> ApiProblem:
    if exc.code == "too_many_attempts":
        retry = exc.retry_after or 60
        return ApiProblem(
            429,
            "too_many_attempts",
            "Too many failed attempts; try again later",
            headers={"Retry-After": str(retry)},
            extra={"retry_after": retry},
        )
    if exc.code == "invalid_credentials":
        return ApiProblem(401, "invalid_credentials", "Invalid username, password or code")
    if exc.code == "no_pending_enrollment":
        return ApiProblem(409, "no_pending_enrollment", "Start the enrollment first")
    return ApiProblem(400, exc.code, "The code or password is not valid")


def session_payload(auth: AuthService, session: AuthSession) -> dict[str, Any]:
    return {
        "user": {
            "id": session.user_id,
            "username": session.username,
            "role": session.role,
            "locale": session.locale,
            "timezone": session.timezone,
        },
        "csrf_token": auth.csrf_token(session),
        "expires_at": session.idle_expires_at.isoformat(),
        "absolute_expires_at": session.expires_at.isoformat(),
        "idle_timeout_seconds": int(IDLE_TIMEOUT.total_seconds()),
        "step_up_until": session.step_up_until.isoformat() if session.step_up_until else None,
    }


@router.post("/login")
def login(body: LoginBody, request: Request, response: Response, ctx: Context) -> dict[str, Any]:
    check_origin(request, ctx.settings)
    try:
        session, token = ctx.auth.login(
            body.username,
            body.password,
            body.code,
            ip=client_ip(request),
            user_agent=request.headers.get("user-agent", ""),
        )
    except AuthFailure as exc:
        raise _problem(exc) from None
    response.set_cookie(
        session_cookie_name(ctx.settings),
        token,
        max_age=int(ABSOLUTE_TIMEOUT.total_seconds()),
        path="/",
        secure=ctx.settings.is_production,
        httponly=True,
        samesite="strict",
    )
    return session_payload(ctx.auth, session)


@router.get("/session")
def get_session(ctx: Context, session: CurrentSession) -> dict[str, Any]:
    return session_payload(ctx.auth, session)


@router.post("/logout", status_code=204)
def logout(response: Response, ctx: Context, session: CsrfSession) -> None:
    ctx.auth.logout(session)
    response.delete_cookie(
        session_cookie_name(ctx.settings),
        path="/",
        secure=ctx.settings.is_production,
        httponly=True,
        samesite="strict",
    )


@router.post("/step-up")
def step_up(body: CodeBody, ctx: Context, session: CsrfSession) -> dict[str, str]:
    try:
        until = ctx.auth.step_up(session, body.code)
    except AuthFailure as exc:
        raise _problem(exc) from None
    return {"step_up_until": until.isoformat()}


@router.post("/totp/enroll")
def totp_enroll(body: PasswordBody, ctx: Context, session: StepUpSession) -> dict[str, str]:
    """Start re-enrollment. Needs a recent step-up (current code) and the password."""
    try:
        enrollment = ctx.auth.start_totp_enrollment(session, body.password)
    except AuthFailure as exc:
        raise _problem(exc) from None
    svg = qrcode.make(enrollment.uri, image_factory=qrcode.image.svg.SvgPathImage).to_string()
    return {
        "secret": enrollment.secret,
        "otpauth_uri": enrollment.uri,
        "qr_svg": "data:image/svg+xml;base64," + base64.b64encode(svg).decode("ascii"),
    }


@router.post("/totp/confirm", status_code=204)
def totp_confirm(body: CodeBody, ctx: Context, session: CsrfSession) -> None:
    try:
        ctx.auth.confirm_totp_enrollment(session, body.code)
    except AuthFailure as exc:
        raise _problem(exc) from None
