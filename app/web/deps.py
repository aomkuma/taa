"""Shared state and FastAPI dependencies of the web service."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from app.config import WebSettings
from app.core.clock import Clock
from app.storage.audit import AuditLog
from app.storage.database import Database

WEB_AUDIT_CHAIN = "web"


@dataclass(frozen=True)
class WebContext:
    settings: WebSettings
    db: Database
    clock: Clock
    audit: AuditLog


def get_context(request: Request) -> WebContext:
    ctx: WebContext = request.app.state.ctx
    return ctx
