"""Learning reports of the owner's engine (PLAN_LEARNING §L19.2, §L20.0, §L20.7; TAA-L701, L801, L808).

- ``GET /engines/{id}/learning/timing?scope=&days=&run=&variant=&strategy=&symbol=``: why losing trades lost
  (EARLY / LATE / STALL / TF_MISMATCH / WRONG …) next to the random-walk baseline;
- ``GET /engines/{id}/learning/expectancy`` with the same query: E[R] = p·W − (1 − p)·L − c, per strategy ×
  symbol, and which lever moved against the previous period;
- ``GET /engines/{id}/learning/behavior?days=``: patterns in the owner's closed manual trades.

Read-only and hypothetical, like the analytics (TAA-1005); nothing here changes a setting.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query
from starlette.concurrency import run_in_threadpool

from app.web.analytics import DEFAULT_DAYS, MAX_DAYS
from app.web.deps import Context, OwnedEngine
from app.web.errors import ApiProblem
from app.web.learning import LearningReports
from app.web.readmodels import QueryError

router = APIRouter(prefix="/engines/{engine_id}/learning", tags=["learning"])

Scope = Annotated[str, Query(min_length=4, max_length=10)]
Days = Annotated[int, Query(ge=1, le=MAX_DAYS)]
Run = Annotated[str | None, Query(min_length=1, max_length=36)]
Variant = Annotated[str, Query(min_length=4, max_length=8)]
Name = Annotated[str | None, Query(min_length=1, max_length=64)]


async def _run(fn: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
    try:
        result: dict[str, Any] = await run_in_threadpool(fn, *args, **kwargs)
    except QueryError as exc:
        raise ApiProblem(400, "invalid_query", str(exc)) from exc
    except LookupError as exc:
        raise ApiProblem(404, "backtest_not_found", "No such backtest run of this engine") from exc
    return result


@router.get("/timing")
async def timing(
    engine: OwnedEngine,
    ctx: Context,
    scope: Scope = "SHADOW",
    days: Days = DEFAULT_DAYS,
    run: Run = None,
    variant: Variant = "PLAN",
    strategy: Name = None,
    symbol: Name = None,
) -> dict[str, Any]:
    return await _run(
        LearningReports(ctx.db, ctx.clock).timing,
        engine.engine_id,
        scope=scope,
        days=days,
        run_id=run,
        variant=variant,
        strategy=strategy,
        symbol=symbol,
    )


@router.get("/expectancy")
async def expectancy(
    engine: OwnedEngine,
    ctx: Context,
    scope: Scope = "SHADOW",
    days: Annotated[int, Query(ge=1, le=MAX_DAYS // 2)] = DEFAULT_DAYS,
    run: Run = None,
    variant: Variant = "PLAN",
    strategy: Name = None,
    symbol: Name = None,
) -> dict[str, Any]:
    return await _run(
        LearningReports(ctx.db, ctx.clock).expectancy,
        engine.engine_id,
        scope=scope,
        days=days,
        run_id=run,
        variant=variant,
        strategy=strategy,
        symbol=symbol,
    )


@router.get("/behavior")
async def behavior(engine: OwnedEngine, ctx: Context, days: Days = DEFAULT_DAYS) -> dict[str, Any]:
    return await _run(
        LearningReports(ctx.db, ctx.clock).behavior, engine.engine_id, engine.owner_user_id, days=days
    )
