"""``/api/v1/engines/{engine_id}/commands``: remote control of the user's own engine (TAA-805).

PLAN §A13 "Commands" and §A32.

- ``POST /commands`` (``StepUpSession``) queues one command from the engine's allowlist; 202 with the
  command. Body ``{type, reason?, strategy?, ticket?, code?}``; each type takes exactly its own fields:

  | type | fields |
  |---|---|
  | KILL_SWITCH_ACTIVATE | reason |
  | STRATEGY_DISABLE | strategy, optional reason |
  | RESYNC, RESCAN_SUITABILITY | none |
  | POSITION_CLOSE | ticket, code |
  | FLATTEN_ALL | reason, code |

  ``code`` is the **engine's** control TOTP (``CONTROL_TOTP_SECRET``, never known to the cloud), checked once
  by the engine; the cloud only carries it until the command is answered or expires (at most 120 s).
- ``GET /commands`` (paginated, newest first, ``status`` filter) and ``GET /commands/{id}``: queue state and
  the engine's result. A TOTP code is never returned.

Risk-increasing commands do not exist here: the type must be on the allowlist, and the queue refuses the
named risk-increasing types besides. Rights come from owning the engine (``OwnedEngine``: anyone else's
engine is 404 ``engine_not_found``), not from the role (§A32 amends §A30). Every queued command is appended
to the ``web`` audit chain (``COMMAND_QUEUED``, without the code); results follow from the ingest API
(``COMMAND_RESULT``).

Errors: 400 ``invalid_command`` (missing or extra fields for the type), 409 ``engine_revoked``, 403
``step_up_required``, 404 ``command_not_found``; 422 for a body that does not parse (unknown type, bad
formats).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from app.sync.command_queue import CommandRefused, public
from app.sync.commands import TOTP_REQUIRED, CommandType
from app.web.deps import Context, OwnedEngine, StepUpSession, no_admin_controls
from app.web.errors import ApiProblem
from app.web.readmodels import MAX_LIMIT, QueryError, ReadModels

router = APIRouter(prefix="/engines/{engine_id}", tags=["control"])

# The fields each command type takes; (required, optional).
FIELDS: dict[CommandType, tuple[frozenset[str], frozenset[str]]] = {
    CommandType.KILL_SWITCH_ACTIVATE: (frozenset({"reason"}), frozenset()),
    CommandType.STRATEGY_DISABLE: (frozenset({"strategy"}), frozenset({"reason"})),
    CommandType.RESYNC: (frozenset(), frozenset()),
    CommandType.RESCAN_SUITABILITY: (frozenset(), frozenset()),
    CommandType.POSITION_CLOSE: (frozenset({"ticket", "code"}), frozenset()),
    CommandType.FLATTEN_ALL: (frozenset({"reason", "code"}), frozenset()),
}


class CommandBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: CommandType
    reason: str | None = Field(None, min_length=1, max_length=200)
    strategy: str | None = Field(None, min_length=1, max_length=64)
    ticket: int | None = Field(None, ge=1, lt=2**63)
    code: str | None = Field(None, pattern=r"^\d{6}$")

    def params(self) -> dict[str, Any]:
        """The command's params, checked against :data:`FIELDS`; raises ``ApiProblem`` 400."""
        given = {k for k in ("reason", "strategy", "ticket", "code") if getattr(self, k) is not None}
        required, optional = FIELDS[self.type]
        missing, extra = required - given, given - required - optional
        if missing or extra:
            parts = [f"missing {', '.join(sorted(missing))}"] if missing else []
            parts += [f"not used by {self.type.value}: {', '.join(sorted(extra))}"] if extra else []
            raise ApiProblem(400, "invalid_command", "; ".join(parts))
        if self.reason is not None and not self.reason.strip():
            raise ApiProblem(400, "invalid_command", "reason must not be blank")
        out: dict[str, Any] = {}
        if self.reason is not None:
            out["reason"] = self.reason.strip()
        if self.strategy is not None:
            out["strategy"] = self.strategy
        if self.ticket is not None:
            out["ticket"] = self.ticket
        return out


@router.post("/commands", status_code=202)
async def queue_command(
    body: CommandBody, engine: OwnedEngine, session: StepUpSession, ctx: Context
) -> dict[str, Any]:
    no_admin_controls(session)
    params = body.params()
    if engine.status != "ACTIVE":
        raise ApiProblem(409, "engine_revoked", "This engine was revoked and takes no commands")
    queue = ctx.engine.commands
    totp = body.code if body.type in TOTP_REQUIRED else None
    try:
        queued = await run_in_threadpool(
            queue.enqueue, engine.engine_id, body.type.value, params, created_by=session.username, totp=totp
        )
    except CommandRefused as exc:  # defence in depth: the body model already admits only allowed types
        raise ApiProblem(400, "invalid_command", str(exc)) from exc
    await run_in_threadpool(
        ctx.audit.append,
        "COMMAND_QUEUED",
        session.username,
        {
            "engine_id": engine.engine_id,
            "command_id": queued["id"],
            "type": body.type.value,
            "params": params,
        },
    )
    row = await run_in_threadpool(queue.get, queued["id"])
    if row is None:  # written a moment ago in this process
        raise ApiProblem(500, "internal_error", "The command was not stored")
    return public(row)


@router.get("/commands")
async def list_commands(
    engine: OwnedEngine,
    ctx: Context,
    status: Annotated[
        str | None, Query(pattern="^(QUEUED|DELIVERED|EXECUTED|REJECTED|FAILED|EXPIRED)$")
    ] = None,
    limit: Annotated[int | None, Query(ge=1, le=MAX_LIMIT)] = None,
    cursor: Annotated[str | None, Query(max_length=256)] = None,
) -> dict[str, Any]:
    await run_in_threadpool(ctx.engine.commands.expire)
    try:
        page = await run_in_threadpool(
            ReadModels(ctx.db).commands, engine.engine_id, status=status, limit=limit, cursor=cursor
        )
    except QueryError as exc:
        raise ApiProblem(400, "invalid_query", str(exc)) from exc
    return dict(page.to_dict())


@router.get("/commands/{command_id}")
async def get_command(engine: OwnedEngine, ctx: Context, command_id: str) -> dict[str, Any]:
    await run_in_threadpool(ctx.engine.commands.expire)
    row = await run_in_threadpool(ctx.engine.commands.get, command_id[:64])
    if row is None or row.engine_id != engine.engine_id:
        raise ApiProblem(404, "command_not_found", "No such command")
    return public(row)
