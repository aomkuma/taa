"""Advisory APIs for the PWA (PLAN §A25–§A31; TAA-809).

User-level (the session user's own preferences; mutations need CSRF):

- ``GET|PUT /advisory/preferences``: the whole :class:`AdvisoryPreferences` document (PUT validates it against
  the detector and strategy catalogs; 400 ``invalid_preferences``)
- ``PUT /advisory/preferences/theories``: only the theory selection (presets, family/detector toggles, params)
- ``POST /advisory/watchlists``, ``PUT|DELETE /advisory/watchlists/{name}``: watchlists (409
  ``watchlist_exists``, 404 ``watchlist_not_found``); ``POST /advisory/favourites/{symbol}``: toggles the
  symbol in the favourites list (created when missing)
- ``GET /advisory/detectors``: the detector catalog (id, name, family, tier, prerequisites, default params)
  and the pattern strategies

Engine-level (``OwnedEngine``; ``server`` defaults to the engine's newest ranking or opportunity server):

- ``ranking`` (latest snapshot, filters), ``ranking/{symbol}`` (scores, gates, metrics), ``ranking/{symbol}/
  history?hours``
- ``opportunities`` (filters, paginated) and ``opportunities/{id}``: evidence, confluence, the win
  probability with per-theory contributions for this user's theory selection, and the shadow results
- ``shadow-trades`` (filters, paginated), ``accuracy``, ``threshold-explorer``, ``theory-scoreboard``,
  ``calibration``: shadow statistics are hypothetical and labelled so

The engine's own ``GET /api/v1/engine/advisory-config`` lives in ``app/web/routers/engine.py``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query, Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.advisory.preferences import AdvisoryPreferences, TheoryPreferences, Watchlist, WatchlistKind
from app.core.errors import ConfigError
from app.web.advisory import AdvisoryReads, PreferenceStore, detector_catalog
from app.web.deps import Context, CsrfSession, CurrentSession, OwnedEngine, WebContext
from app.web.entitlements import EntitlementError, EntitlementService
from app.web.errors import ApiProblem
from app.web.readmodels import MAX_LIMIT, QueryError

router = APIRouter(tags=["advisory"])

Limit = Annotated[int | None, Query(ge=1, le=MAX_LIMIT)]
Cursor = Annotated[str | None, Query(max_length=256)]
Name = Annotated[str | None, Query(min_length=1, max_length=64)]
Server = Annotated[str | None, Query(min_length=1, max_length=64)]


async def _run(fn: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return await run_in_threadpool(fn, *args, **kwargs)
    except QueryError as exc:
        raise ApiProblem(400, "invalid_query", str(exc)) from exc
    except ConfigError as exc:
        raise ApiProblem(400, "invalid_preferences", str(exc)) from exc


def _store(ctx: WebContext) -> PreferenceStore:
    return PreferenceStore(ctx.db)


async def _save(ctx: WebContext, user_id: str, prefs: AdvisoryPreferences) -> dict[str, Any]:
    service = EntitlementService(ctx.db, ctx.clock)
    try:  # the plan's watchlist count and size (PLAN §A30; TAA-8A2)
        ent = await run_in_threadpool(service.resolve, user_id)
        service.check_preferences(ent, prefs)
    except EntitlementError as exc:
        raise ApiProblem(403, "plan_limit", str(exc), extra={"key": exc.key}) from exc
    saved: AdvisoryPreferences = await _run(_store(ctx).save, user_id, prefs, ctx.clock.now_utc())
    return saved.model_dump(mode="json")


def _rebuild(prefs: AdvisoryPreferences, **changes: Any) -> AdvisoryPreferences:
    """A copy with *changes*, validated again (model_copy alone skips validation)."""
    try:
        return AdvisoryPreferences.model_validate(prefs.model_dump(mode="json") | changes)
    except ValidationError as exc:
        raise ApiProblem(400, "invalid_preferences", str(exc.errors()[0]["msg"])) from exc


# --- preferences --------------------------------------------------------------------------------------------


@router.get("/advisory/preferences")
async def get_preferences(ctx: Context, session: CurrentSession) -> dict[str, Any]:
    prefs: AdvisoryPreferences = await run_in_threadpool(_store(ctx).get, session.user_id)
    return prefs.model_dump(mode="json")


@router.put("/advisory/preferences")
async def put_preferences(body: dict[str, Any], ctx: Context, session: CsrfSession) -> dict[str, Any]:
    prefs = await _run(PreferenceStore.validate, body)
    return await _save(ctx, session.user_id, prefs)


@router.put("/advisory/preferences/theories")
async def put_theories(body: TheoryPreferences, ctx: Context, session: CsrfSession) -> dict[str, Any]:
    prefs: AdvisoryPreferences = await run_in_threadpool(_store(ctx).get, session.user_id)
    return await _save(ctx, session.user_id, _rebuild(prefs, theories=body.model_dump(mode="json")))


@router.get("/advisory/detectors")
async def detectors(session: CurrentSession) -> dict[str, Any]:
    result: dict[str, Any] = await run_in_threadpool(detector_catalog)
    return result


# --- watchlists ---------------------------------------------------------------------------------------------


def _lists(prefs: AdvisoryPreferences) -> list[dict[str, Any]]:
    return [w.model_dump(mode="json") for w in prefs.watchlists]


@router.post("/advisory/watchlists", status_code=201)
async def add_watchlist(body: Watchlist, ctx: Context, session: CsrfSession) -> dict[str, Any]:
    prefs: AdvisoryPreferences = await run_in_threadpool(_store(ctx).get, session.user_id)
    if prefs.watchlist(body.name) is not None:
        raise ApiProblem(409, "watchlist_exists", "A watchlist with this name exists")
    saved = await _save(
        ctx, session.user_id, _rebuild(prefs, watchlists=[*_lists(prefs), body.model_dump(mode="json")])
    )
    return {"watchlists": saved["watchlists"]}


@router.put("/advisory/watchlists/{name}")
async def put_watchlist(name: str, body: Watchlist, ctx: Context, session: CsrfSession) -> dict[str, Any]:
    prefs: AdvisoryPreferences = await run_in_threadpool(_store(ctx).get, session.user_id)
    current = prefs.watchlist(name)
    if current is None:
        raise ApiProblem(404, "watchlist_not_found", "No such watchlist")
    lists = [
        body.model_dump(mode="json") if w is current else w.model_dump(mode="json") for w in prefs.watchlists
    ]
    saved = await _save(ctx, session.user_id, _rebuild(prefs, watchlists=lists))
    return {"watchlists": saved["watchlists"]}


@router.delete("/advisory/watchlists/{name}", status_code=204, response_model=None)
async def delete_watchlist(name: str, ctx: Context, session: CsrfSession) -> Response:
    prefs: AdvisoryPreferences = await run_in_threadpool(_store(ctx).get, session.user_id)
    current = prefs.watchlist(name)
    if current is None:
        raise ApiProblem(404, "watchlist_not_found", "No such watchlist")
    lists = [w.model_dump(mode="json") for w in prefs.watchlists if w is not current]
    await _save(ctx, session.user_id, _rebuild(prefs, watchlists=lists))
    return Response(status_code=204)


@router.post("/advisory/favourites/{symbol}")
async def toggle_favourite(symbol: str, ctx: Context, session: CsrfSession) -> dict[str, Any]:
    prefs: AdvisoryPreferences = await run_in_threadpool(_store(ctx).get, session.user_id)
    lists = _lists(prefs)
    fav = next((w for w in lists if w["kind"] == WatchlistKind.FAVOURITES.value), None)
    if fav is None:
        fav = {"name": "Favourites", "kind": WatchlistKind.FAVOURITES.value, "symbols": []}
        lists.insert(0, fav)
    added = symbol not in fav["symbols"]
    fav["symbols"] = [*fav["symbols"], symbol] if added else [s for s in fav["symbols"] if s != symbol]
    await _save(ctx, session.user_id, _rebuild(prefs, watchlists=lists))
    return {"symbol": symbol, "favourite": added, "favourites": fav["symbols"]}


# --- engine data --------------------------------------------------------------------------------------------


def reads(ctx: WebContext) -> AdvisoryReads:
    return AdvisoryReads(ctx.db)


async def _server(ctx: WebContext, engine_id: str, server: str | None) -> str:
    srv = server or await run_in_threadpool(reads(ctx).default_server, engine_id)
    if srv is None:
        raise ApiProblem(404, "advisory_not_found", "The engine has not reported advisory data yet")
    return srv


@router.get("/engines/{engine_id}/ranking")
async def ranking(
    engine: OwnedEngine,
    ctx: Context,
    asset_class: Annotated[str | None, Query(min_length=1, max_length=16)] = None,
    eligible: bool | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = await _run(
        reads(ctx).ranking, engine.engine_id, asset_class=asset_class, eligible=eligible
    )
    return result


@router.get("/engines/{engine_id}/ranking/{symbol}")
async def ranking_symbol(engine: OwnedEngine, ctx: Context, symbol: str) -> dict[str, Any]:
    found: dict[str, Any] | None = await _run(reads(ctx).ranking_symbol, engine.engine_id, symbol[:32])
    if found is None:
        raise ApiProblem(404, "symbol_not_found", "No ranking for this symbol")
    return found


@router.get("/engines/{engine_id}/ranking/{symbol}/history")
async def ranking_history(
    engine: OwnedEngine, ctx: Context, symbol: str, hours: Annotated[int, Query(ge=1)] = 168
) -> dict[str, Any]:
    items = await _run(reads(ctx).ranking_history, engine.engine_id, symbol[:32], hours, ctx.clock.now_utc())
    return {"symbol": symbol, "items": items}


@router.get("/engines/{engine_id}/opportunities")
async def opportunities(
    engine: OwnedEngine,
    ctx: Context,
    status: Annotated[str | None, Query(pattern="^(CANDIDATE|ACTIVE|EXPIRED|INVALIDATED|FOLLOWED)$")] = None,
    symbol: Name = None,
    strategy: Name = None,
    limit: Limit = None,
    cursor: Cursor = None,
) -> dict[str, Any]:
    page = await _run(
        reads(ctx).opportunities,
        engine.engine_id,
        status=status,
        symbol=symbol,
        strategy=strategy,
        limit=limit,
        cursor=cursor,
    )
    return dict(page.to_dict())


@router.get("/engines/{engine_id}/opportunities/{opportunity_id}")
async def opportunity(
    engine: OwnedEngine, ctx: Context, session: CurrentSession, opportunity_id: str
) -> dict[str, Any]:
    prefs = await run_in_threadpool(_store(ctx).get, session.user_id)
    found: dict[str, Any] | None = await _run(
        reads(ctx).opportunity, engine.engine_id, opportunity_id[:64], prefs
    )
    if found is None:
        raise ApiProblem(404, "opportunity_not_found", "No such opportunity")
    return found


@router.get("/engines/{engine_id}/shadow-trades")
async def shadow_trades(
    engine: OwnedEngine,
    ctx: Context,
    status: Annotated[str | None, Query(pattern="^(OPEN|CLOSED|VOID)$")] = None,
    variant: Annotated[str | None, Query(pattern="^(PLAN|MANAGED)$")] = None,
    source: Annotated[str | None, Query(pattern="^(LIVE|REPLAY)$")] = None,
    symbol: Name = None,
    limit: Limit = None,
    cursor: Cursor = None,
) -> dict[str, Any]:
    page = await _run(
        reads(ctx).shadow_trades,
        engine.engine_id,
        status=status,
        variant=variant,
        source=source,
        symbol=symbol,
        limit=limit,
        cursor=cursor,
    )
    return dict(page.to_dict())


Variant = Annotated[str, Query(pattern="^(PLAN|MANAGED)$")]
SourceQ = Annotated[str | None, Query(pattern="^(LIVE|REPLAY)$")]


@router.get("/engines/{engine_id}/accuracy")
async def accuracy(
    engine: OwnedEngine,
    ctx: Context,
    session: CurrentSession,
    server: Server = None,
    variant: Variant = "PLAN",
    since: datetime | None = None,
) -> dict[str, Any]:
    srv = await _server(ctx, engine.engine_id, server)
    prefs = await run_in_threadpool(_store(ctx).get, session.user_id)
    result: dict[str, Any] = await _run(
        reads(ctx).accuracy, engine.engine_id, srv, variant=variant, since=_aware(since), prefs=prefs
    )
    return result


@router.get("/engines/{engine_id}/threshold-explorer")
async def explorer(
    engine: OwnedEngine,
    ctx: Context,
    server: Server = None,
    variant: Variant = "PLAN",
    source: SourceQ = None,
    since: datetime | None = None,
) -> dict[str, Any]:
    srv = await _server(ctx, engine.engine_id, server)
    result: dict[str, Any] = await _run(
        reads(ctx).explorer, engine.engine_id, srv, variant=variant, source=source, since=_aware(since)
    )
    return result


@router.get("/engines/{engine_id}/theory-scoreboard")
async def theory_scoreboard(
    engine: OwnedEngine,
    ctx: Context,
    server: Server = None,
    variant: Variant = "PLAN",
    source: SourceQ = None,
    since: datetime | None = None,
) -> dict[str, Any]:
    srv = await _server(ctx, engine.engine_id, server)
    result: dict[str, Any] = await _run(
        reads(ctx).scoreboard, engine.engine_id, srv, variant=variant, source=source, since=_aware(since)
    )
    return result


@router.get("/engines/{engine_id}/calibration")
async def calibration(engine: OwnedEngine, ctx: Context, server: Server = None) -> dict[str, Any]:
    srv = await _server(ctx, engine.engine_id, server)
    found: dict[str, Any] | None = await _run(reads(ctx).calibration, engine.engine_id, srv)
    if found is None:
        raise ApiProblem(404, "calibration_not_found", "No calibration has been built yet")
    return found


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ApiProblem(400, "invalid_query", "since: a timezone-aware time is required")
    return value
