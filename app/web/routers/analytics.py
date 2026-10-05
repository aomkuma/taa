"""Analytics and recommendations of the owner's engine (PLAN §A15, §A16; TAA-1005).

- ``GET /engines/{id}/analytics?scope=PAPER|SHADOW|BACKTEST&run=&days=&variant=&strategy=&symbol=``: KPIs,
  curves, R distribution, performance by style, MAE/MFE and the P/L attribution summary
  (:func:`app.analytics.report.build_report`).
- ``GET /engines/{id}/recommendations`` with the same query: the A16 rules with evidence, sample sizes and,
  where possible, the fields of a "Backtest this change" job (``POST /engines/{id}/backtests``).

Every scope here is hypothetical and labelled so. Recommendations never change any configuration.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query
from starlette.concurrency import run_in_threadpool

from app.web.analytics import DEFAULT_DAYS, MAX_DAYS, Analytics
from app.web.deps import Context, OwnedEngine
from app.web.errors import ApiProblem
from app.web.readmodels import QueryError

router = APIRouter(prefix="/engines/{engine_id}", tags=["analytics"])

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


@router.get("/analytics")
async def analytics(
    engine: OwnedEngine,
    ctx: Context,
    scope: Scope = "PAPER",
    days: Days = DEFAULT_DAYS,
    run: Run = None,
    variant: Variant = "PLAN",
    strategy: Name = None,
    symbol: Name = None,
) -> dict[str, Any]:
    return await _run(
        Analytics(ctx.db, ctx.clock).report,
        engine.engine_id,
        scope=scope,
        days=days,
        run_id=run,
        variant=variant,
        strategy=strategy,
        symbol=symbol,
    )


@router.get("/recommendations")
async def recommendations(
    engine: OwnedEngine,
    ctx: Context,
    scope: Scope = "PAPER",
    days: Days = DEFAULT_DAYS,
    run: Run = None,
    variant: Variant = "PLAN",
    strategy: Name = None,
    symbol: Name = None,
) -> dict[str, Any]:
    return await _run(
        Analytics(ctx.db, ctx.clock).recommendations,
        engine.engine_id,
        scope=scope,
        days=days,
        run_id=run,
        variant=variant,
        strategy=strategy,
        symbol=symbol,
    )
