"""``/api/v1/engines/{engine_id}/...``: read APIs over the replicated engine data (PLAN §A14, §A32; TAA-803).

Every route takes ``OwnedEngine``: only the session user's own engines resolve, anything else is 404
``engine_not_found``. Lists are paginated (``limit`` ≤ 200, ``cursor`` from ``next_cursor``). Errors:
``invalid_query`` (400) for unusable parameters, ``<thing>_not_found`` (404).

Not served yet, because no engine event carries them: live quotes, account snapshots of the broker account
and heartbeats (TAA-705); notifications (TAA-806); backtests (TAA-807); analytics (TAA-1005).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query
from starlette.concurrency import run_in_threadpool

from app.storage.audit import verify_chain
from app.web.deps import Context, OwnedEngine, WebContext
from app.web.errors import ApiProblem
from app.web.readmodels import MAX_LIMIT, QueryError, ReadModels

router = APIRouter(prefix="/engines/{engine_id}", tags=["data"])

Limit = Annotated[int | None, Query(ge=1, le=MAX_LIMIT)]
Cursor = Annotated[str | None, Query(max_length=256)]
Name = Annotated[str | None, Query(min_length=1, max_length=64)]


async def _run(fn: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return await run_in_threadpool(fn, *args, **kwargs)
    except QueryError as exc:
        raise ApiProblem(400, "invalid_query", str(exc)) from exc


def models(ctx: WebContext) -> ReadModels:
    return ReadModels(ctx.db)


@router.get("/status")
async def status(engine: OwnedEngine, ctx: Context) -> dict[str, Any]:
    body: dict[str, Any] = await _run(models(ctx).status, engine.engine_id)
    return {"engine": engine.public(), **body}


@router.get("/account")
async def account(engine: OwnedEngine, ctx: Context) -> dict[str, Any]:
    result: dict[str, Any] = await _run(models(ctx).account, engine.engine_id)
    return result


@router.get("/positions")
async def positions(
    engine: OwnedEngine,
    ctx: Context,
    status: Annotated[str | None, Query(pattern="^(OPEN|CLOSED)$")] = None,
    symbol: Name = None,
    limit: Limit = None,
    cursor: Cursor = None,
) -> dict[str, Any]:
    page = await _run(
        models(ctx).positions, engine.engine_id, status=status, symbol=symbol, limit=limit, cursor=cursor
    )
    return dict(page.to_dict())


@router.get("/trades")
async def trades(
    engine: OwnedEngine, ctx: Context, symbol: Name = None, limit: Limit = None, cursor: Cursor = None
) -> dict[str, Any]:
    """Closed paper positions, newest exit first (R multiple and net P/L included)."""
    page = await _run(
        models(ctx).positions,
        engine.engine_id,
        status="CLOSED",
        symbol=symbol,
        limit=limit,
        cursor=cursor,
    )
    return dict(page.to_dict())


@router.get("/intents")
async def intents(
    engine: OwnedEngine,
    ctx: Context,
    kind: Annotated[str, Query(pattern="^(paper|broker)$")] = "paper",
    status: Name = None,
    symbol: Name = None,
    limit: Limit = None,
    cursor: Cursor = None,
) -> dict[str, Any]:
    page = await _run(
        models(ctx).intents,
        engine.engine_id,
        kind=kind,
        status=status,
        symbol=symbol,
        limit=limit,
        cursor=cursor,
    )
    return dict(page.to_dict())


@router.get("/decisions")
async def decisions(
    engine: OwnedEngine,
    ctx: Context,
    decision: Annotated[str | None, Query(pattern="^(ACCEPT|REJECT|HOLD)$")] = None,
    symbol: Name = None,
    strategy: Name = None,
    profile: Annotated[str | None, Query(pattern="^(EXECUTION|ADVISORY)$")] = None,
    limit: Limit = None,
    cursor: Cursor = None,
) -> dict[str, Any]:
    """Decisions (each carries its signal), newest first; the detail route adds the checks."""
    page = await _run(
        models(ctx).decisions,
        engine.engine_id,
        decision=decision,
        symbol=symbol,
        strategy=strategy,
        profile=profile,
        limit=limit,
        cursor=cursor,
    )
    return dict(page.to_dict())


@router.get("/decisions/{decision_id}")
async def decision(engine: OwnedEngine, ctx: Context, decision_id: str) -> dict[str, Any]:
    found: dict[str, Any] | None = await _run(models(ctx).decision, engine.engine_id, decision_id[:64])
    if found is None:
        raise ApiProblem(404, "decision_not_found", "No such decision")
    return found


@router.get("/breakers")
async def breakers(
    engine: OwnedEngine, ctx: Context, limit: Limit = None, cursor: Cursor = None
) -> dict[str, Any]:
    result: dict[str, Any] = await _run(models(ctx).breakers, engine.engine_id, limit=limit, cursor=cursor)
    return result


@router.get("/kill-switch")
async def kill_switch(
    engine: OwnedEngine, ctx: Context, limit: Limit = None, cursor: Cursor = None
) -> dict[str, Any]:
    page = await _run(models(ctx).kill_switch, engine.engine_id, limit=limit, cursor=cursor)
    return dict(page.to_dict())


@router.get("/symbols")
async def symbols(
    engine: OwnedEngine,
    ctx: Context,
    asset_class: Annotated[str | None, Query(min_length=1, max_length=16)] = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    items = await _run(models(ctx).symbols, engine.engine_id, asset_class=asset_class, enabled=enabled)
    return {"items": items}


@router.get("/symbols/{symbol}")
async def symbol(engine: OwnedEngine, ctx: Context, symbol: str) -> dict[str, Any]:
    found: dict[str, Any] | None = await _run(models(ctx).symbol, engine.engine_id, symbol[:32])
    if found is None:
        raise ApiProblem(404, "symbol_not_found", "No such symbol")
    return found


@router.get("/candles")
async def candles(
    engine: OwnedEngine,
    ctx: Context,
    symbol: Annotated[str, Query(min_length=1, max_length=32)],
    timeframe: Annotated[str, Query(min_length=2, max_length=3)] = "M15",
    server: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=2000)] = 300,
    overlays: Annotated[str, Query(max_length=200)] = "",
    zones: bool = False,
) -> dict[str, Any]:
    """Closed bars with indicator overlays (``overlays=ema:20,bb:20,rsi:14``), decision/trade markers
    and, with ``zones=true``, the S/R zones at the last shown bar."""
    for value, name in ((start, "start"), (end, "end")):
        if value is not None and value.tzinfo is None:
            raise ApiProblem(400, "invalid_query", f"{name}: a timezone-aware time is required")
    rm = models(ctx)
    srv = server or await _run(rm.default_server, engine.engine_id, symbol)
    if srv is None:
        raise ApiProblem(404, "candles_not_found", "No candles for this symbol yet")
    result: dict[str, Any] = await _run(
        rm.candles,
        engine.engine_id,
        server=srv,
        symbol=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
        limit=limit,
        overlays=[o for o in overlays.split(",") if o.strip()],
        zones=zones,
    )
    return result


@router.get("/config")
async def config(engine: OwnedEngine, ctx: Context) -> dict[str, Any]:
    """The engine's effective configuration of its latest run, secrets masked."""
    found: dict[str, Any] | None = await _run(models(ctx).config, engine.engine_id)
    if found is None:
        raise ApiProblem(404, "config_not_found", "The engine has not reported a configuration yet")
    return found


@router.get("/audit/verify")
async def audit_verify(engine: OwnedEngine, ctx: Context) -> dict[str, Any]:
    """Re-verify the replicated audit chain end to end (the stored status is in ``/status``)."""
    report = await run_in_threadpool(verify_chain, ctx.db, f"engine:{engine.engine_id}")
    return {
        "chain": report.chain,
        "ok": report.ok,
        "events_checked": report.events_checked,
        "first_bad_seq": report.first_bad_seq,
        "detail": report.detail,
    }
