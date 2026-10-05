"""The owner's manual MT5 trades and their signals (PLAN §A34; TAA-1006).

- ``GET /engines/{id}/manual-trades?status=OPEN|CLOSED&limit=``: the engine's links with the owner's
  corrections, the effective signal and, for closed trades, "signal vs bot vs me" in R.
- ``GET /engines/{id}/manual-trades/{position_id}/candidates``: the signals the owner can pick.
- ``PUT /engines/{id}/manual-trades/{position_id}/link`` ``{choice, signal_key?}`` (CSRF): correct a link;
  ``DELETE`` the same path goes back to the engine's match. Both are audited on the web chain.

Only the engine's owner reads or corrects them (``OwnedEngine``). A link never changes trading.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from app.web.deps import Context, CsrfSession, OwnedEngine, WebContext
from app.web.errors import ApiProblem
from app.web.manual_trades import CHOICES, ManualTrades
from app.web.readmodels import QueryError

router = APIRouter(prefix="/engines/{engine_id}/manual-trades", tags=["manual"])


class LinkBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    choice: str = Field(min_length=1, max_length=16)
    signal_key: str | None = Field(default=None, min_length=1, max_length=64)


def trades(ctx: WebContext) -> ManualTrades:
    return ManualTrades(ctx.db, ctx.clock)


async def _run(fn: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return await run_in_threadpool(fn, *args, **kwargs)
    except QueryError as exc:
        raise ApiProblem(400, "invalid_query", str(exc)) from exc
    except LookupError as exc:
        raise ApiProblem(404, "manual_trade_not_found", "No such manual trade") from exc


@router.get("")
async def list_trades(
    engine: OwnedEngine,
    ctx: Context,
    status: Annotated[str | None, Query(min_length=4, max_length=6)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    result: dict[str, Any] = await _run(trades(ctx).list, engine.engine_id, status=status, limit=limit)
    return result


@router.get("/{position_id}/candidates")
async def candidates(engine: OwnedEngine, ctx: Context, position_id: int) -> dict[str, Any]:
    result: dict[str, Any] = await _run(trades(ctx).candidates, engine.engine_id, position_id)
    return result


@router.put("/{position_id}/link")
async def set_link(
    engine: OwnedEngine, ctx: Context, session: CsrfSession, position_id: int, body: LinkBody
) -> dict[str, Any]:
    if body.choice not in CHOICES:
        raise ApiProblem(400, "invalid_query", "choice: CONFIRMED, OWN_IDEA or SIGNAL")
    result: dict[str, Any] = await _run(
        trades(ctx).save_override,
        engine.engine_id,
        position_id,
        choice=body.choice,
        signal_key=body.signal_key,
        user_id=session.user_id,
    )
    ctx.audit.append(
        "manual_trade.link",
        session.username,
        {
            "engine": engine.engine_id,
            "position": position_id,
            "choice": body.choice,
            "signal": body.signal_key,
        },
    )
    return result


@router.delete("/{position_id}/link")
async def clear_link(
    engine: OwnedEngine, ctx: Context, session: CsrfSession, position_id: int
) -> dict[str, Any]:
    result: dict[str, Any] = await _run(trades(ctx).clear_override, engine.engine_id, position_id)
    ctx.audit.append(
        "manual_trade.link_cleared", session.username, {"engine": engine.engine_id, "position": position_id}
    )
    return result
