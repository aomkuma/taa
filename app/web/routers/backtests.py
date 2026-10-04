"""Backtests on an engine's uploaded history (PLAN §A14 "API", §A17; TAA-807).

- ``GET /backtests/presets``: the presets and the request limits (for the PWA's form)
- ``POST /engines/{id}/backtests`` (CSRF): 202 with the QUEUED run. Body :class:`BacktestRequest`; 400
  ``invalid_backtest`` (unknown strategies, a period that has not ended), 409 ``backtest_limit`` (open runs
  per user), 422 for a body that does not validate
- ``GET /engines/{id}/backtests``: runs, newest first (paginated); ``GET .../backtests/{run_id}``: summary and
  equity curve; ``GET .../backtests/{run_id}/trades?offset&limit``: the stored trades
- ``GET /engines/{id}/backtests/compare?ids=a,b[,c,d]``: finished runs side by side (request, metrics,
  provenance)

All engine routes take ``OwnedEngine`` (anyone else's engine: 404). Results are hypothetical: the summary
carries the backtester's documented limitations.
"""

from __future__ import annotations

from typing import Annotated, Any, get_args

from fastapi import APIRouter, Query
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.backtest.presets import MAX_PERIOD, PRESETS, BacktestRequest, PresetName
from app.core.errors import ConfigError
from app.storage.models import BacktestRunRow
from app.web.deps import Context, CsrfSession, CurrentSession, OwnedEngine, WebContext
from app.web.errors import ApiProblem
from app.web.readmodels import MAX_LIMIT, QueryError, paginate
from app.worker.backtests import MAX_OPEN_RUNS, BacktestLimit, BacktestService, run_dict
from app.worker.jobs import JobQueue

router = APIRouter(tags=["backtests"])


def service(ctx: WebContext) -> BacktestService:
    return BacktestService(ctx.db, ctx.clock, JobQueue(ctx.db, ctx.clock))


@router.get("/backtests/presets")
async def presets(session: CurrentSession) -> dict[str, Any]:
    return {
        "presets": [p for p in get_args(PresetName) if p in PRESETS],
        "max_symbols": 5,
        "max_days": MAX_PERIOD.days,
        "max_open_runs": MAX_OPEN_RUNS,
    }


@router.post("/engines/{engine_id}/backtests", status_code=202)
async def create(
    body: BacktestRequest, engine: OwnedEngine, ctx: Context, session: CsrfSession
) -> dict[str, Any]:
    try:
        run: dict[str, Any] = await run_in_threadpool(
            service(ctx).create, session.user_id, engine.engine_id, body, created_by=session.username
        )
    except BacktestLimit as exc:
        raise ApiProblem(409, "backtest_limit", str(exc)) from exc
    except ConfigError as exc:
        raise ApiProblem(400, "invalid_backtest", str(exc)) from exc
    return run


@router.get("/engines/{engine_id}/backtests")
async def list_runs(
    engine: OwnedEngine,
    ctx: Context,
    limit: Annotated[int | None, Query(ge=1, le=MAX_LIMIT)] = None,
    cursor: Annotated[str | None, Query(max_length=256)] = None,
) -> dict[str, Any]:
    def load() -> dict[str, Any]:
        with ctx.db.session() as sess:
            return paginate(
                sess,
                BacktestRunRow,
                [BacktestRunRow.engine_id == engine.engine_id],
                BacktestRunRow.created_at,
                BacktestRunRow.run_id,
                limit=limit,
                cursor=cursor,
                serialize=run_dict,
            ).to_dict()

    try:
        result: dict[str, Any] = await run_in_threadpool(load)
    except QueryError as exc:
        raise ApiProblem(400, "invalid_query", str(exc)) from exc
    return result


def _runs(ctx: WebContext, engine_id: str, run_ids: list[str]) -> list[BacktestRunRow]:
    with ctx.db.session() as sess:
        rows = {
            r.run_id: r
            for r in sess.scalars(
                select(BacktestRunRow).where(
                    BacktestRunRow.engine_id == engine_id, BacktestRunRow.run_id.in_(run_ids)
                )
            )
        }
    missing = [i for i in run_ids if i not in rows]
    if missing:
        raise ApiProblem(404, "backtest_not_found", f"No such backtest: {missing[0]}")
    return [rows[i] for i in run_ids]


@router.get("/engines/{engine_id}/backtests/compare")
async def compare(
    engine: OwnedEngine, ctx: Context, ids: Annotated[str, Query(min_length=1, max_length=200)]
) -> dict[str, Any]:
    run_ids = list(dict.fromkeys(i.strip()[:36] for i in ids.split(",") if i.strip()))
    if not 2 <= len(run_ids) <= 4:
        raise ApiProblem(400, "invalid_query", "ids: 2-4 backtest ids")
    rows = await run_in_threadpool(_runs, ctx, engine.engine_id, run_ids)
    unfinished = [r.run_id for r in rows if r.status != "DONE"]
    if unfinished:
        raise ApiProblem(409, "backtest_not_finished", f"Not finished: {', '.join(unfinished)}")
    return {
        "runs": [
            {
                "run_id": r.run_id,
                "preset": r.preset,
                "request": dict(r.request),
                "metrics": dict(r.summary).get("metrics"),
                "provenance": dict(r.summary).get("provenance"),
                "trades_total": r.trades_total,
            }
            for r in rows
        ]
    }


@router.get("/engines/{engine_id}/backtests/{run_id}")
async def detail(engine: OwnedEngine, ctx: Context, run_id: str) -> dict[str, Any]:
    [row] = await run_in_threadpool(_runs, ctx, engine.engine_id, [run_id[:36]])
    return run_dict(row, full=True)


@router.get("/engines/{engine_id}/backtests/{run_id}/trades")
async def trades(
    engine: OwnedEngine,
    ctx: Context,
    run_id: str,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 100,
) -> dict[str, Any]:
    [row] = await run_in_threadpool(_runs, ctx, engine.engine_id, [run_id[:36]])
    stored = list(row.trades)
    return {
        "items": stored[offset : offset + limit],
        "offset": offset,
        "stored": len(stored),
        "total": row.trades_total,
    }
