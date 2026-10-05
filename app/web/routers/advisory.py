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
from pydantic import BaseModel, ConfigDict, ValidationError
from starlette.concurrency import run_in_threadpool

from app.advisory.preferences import (
    AdvisoryPreferences,
    EntryPlanPreferences,
    TheoryPreferences,
    TradingProfile,
    Watchlist,
    WatchlistKind,
)
from app.config import load_app_config
from app.core.enums import Side
from app.core.errors import ConfigError
from app.storage.models import AccountProfileRow
from app.web.account_profiles import load_profile, plan_of, preview_plan, size_manual
from app.web.advisory import AdvisoryReads, PreferenceStore, detector_catalog
from app.web.deps import AdvisoryEngine, Context, CsrfSession, CurrentSession, WebContext
from app.web.entitlements import EntitlementError, EntitlementService
from app.web.errors import ApiProblem
from app.web.feed import redact
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
# ``AdvisoryEngine``: the user's own engine, or the market feed for a subscriber without one (TAA-8A4). On the
# feed, the engine owner's account details are redacted and the user gets their own figures instead.

OWNER_METRICS = frozenset(
    {"lot", "risk_money", "risk_budget", "margin", "effective_leverage", "required_equity"}
)


def reads(ctx: WebContext) -> AdvisoryReads:
    return AdvisoryReads(ctx.db)


async def _server(ctx: WebContext, engine_id: str, server: str | None) -> str:
    srv = server or await run_in_threadpool(reads(ctx).default_server, engine_id)
    if srv is None:
        raise ApiProblem(404, "advisory_not_found", "The engine has not reported advisory data yet")
    return srv


def _risk_percent(ctx: WebContext, user_id: str, profile: Any) -> float:
    """The lowest of config.yaml's risk per trade, the trading profile's and the account profile's risk per
    signal: the same cap the sizer applies, so the ranking and the sizing agree."""
    prefs = PreferenceStore(ctx.db).get(user_id)
    values = [
        load_app_config().risk.max_risk_per_trade_percent,
        prefs.trading_profile.resolve().risk_per_signal_percent,
    ]
    if profile is not None and profile.risk_percent is not None:
        values.append(profile.risk_percent)
    return min(values)


@router.get("/engines/{engine_id}/ranking")
async def ranking(
    engine: AdvisoryEngine,
    ctx: Context,
    session: CurrentSession,
    asset_class: Annotated[str | None, Query(min_length=1, max_length=16)] = None,
    eligible: bool | None = None,
) -> dict[str, Any]:
    if engine.is_owner:
        result: dict[str, Any] = await _run(
            reads(ctx).ranking, engine.engine_id, asset_class=asset_class, eligible=eligible
        )
        return result
    profile = await run_in_threadpool(load_profile, ctx.db, session.user_id)
    risk = await run_in_threadpool(_risk_percent, ctx, session.user_id, profile)
    personal: dict[str, Any] = await _run(
        reads(ctx).personal_ranking,
        engine.engine_id,
        profile,
        risk,
        ctx.clock.now_utc(),
        asset_class=asset_class,
    )
    if eligible is not None:
        personal["items"] = [i for i in personal["items"] if i["personal"].get("eligible") is eligible]
    return personal


@router.get("/engines/{engine_id}/ranking/{symbol}")
async def ranking_symbol(engine: AdvisoryEngine, ctx: Context, symbol: str) -> dict[str, Any]:
    found: dict[str, Any] | None = await _run(reads(ctx).ranking_symbol, engine.engine_id, symbol[:32])
    if found is None:
        raise ApiProblem(404, "symbol_not_found", "No ranking for this symbol")
    if not engine.is_owner:  # the owner's lot, budget and margin stay private
        payload = dict(found.get("payload") or {})
        metrics = {k: v for k, v in dict(payload.get("metrics") or {}).items() if k not in OWNER_METRICS}
        found["payload"] = payload | {"metrics": metrics}
    return found


@router.get("/engines/{engine_id}/ranking/{symbol}/history")
async def ranking_history(
    engine: AdvisoryEngine, ctx: Context, symbol: str, hours: Annotated[int, Query(ge=1)] = 168
) -> dict[str, Any]:
    items = await _run(reads(ctx).ranking_history, engine.engine_id, symbol[:32], hours, ctx.clock.now_utc())
    return {"symbol": symbol, "items": items}


@router.get("/engines/{engine_id}/opportunities")
async def opportunities(
    engine: AdvisoryEngine,
    ctx: Context,
    session: CurrentSession,
    status: Annotated[str | None, Query(pattern="^(CANDIDATE|ACTIVE|EXPIRED|INVALIDATED|FOLLOWED)$")] = None,
    symbol: Name = None,
    strategy: Name = None,
    limit: Limit = None,
    cursor: Cursor = None,
) -> dict[str, Any]:
    prefs = await run_in_threadpool(_store(ctx).get, session.user_id)
    page: Any = await _run(
        reads(ctx).opportunities,
        engine.engine_id,
        status=status,
        symbol=symbol,
        strategy=strategy,
        limit=limit,
        cursor=cursor,
        prefs=prefs,
    )
    out = dict(page.to_dict())
    if not engine.is_owner:
        out["items"] = [redact(i) for i in out["items"]]
    return out


@router.get("/engines/{engine_id}/opportunities/{opportunity_id}")
async def opportunity(
    engine: AdvisoryEngine, ctx: Context, session: CurrentSession, opportunity_id: str
) -> dict[str, Any]:
    prefs = await run_in_threadpool(_store(ctx).get, session.user_id)
    found: dict[str, Any] | None = await _run(
        reads(ctx).opportunity, engine.engine_id, opportunity_id[:64], prefs
    )
    if found is None:
        raise ApiProblem(404, "opportunity_not_found", "No such opportunity")
    if not engine.is_owner:
        found = redact(found)
        found["shadow"] = [redact(s) for s in found.get("shadow", [])]
        found["my_sizing"] = await run_in_threadpool(
            _my_sizing, ctx, engine.engine_id, session.user_id, found
        )
    return found


def _my_sizing(ctx: WebContext, engine_id: str, user_id: str, opp: dict[str, Any]) -> dict[str, Any]:
    """The opportunity sized for the user's MANUAL account profile (TAA-8A3)."""
    profile = load_profile(ctx.db, user_id)
    if profile is None or profile.source != "MANUAL":
        return {"available": False, "reason": "no_manual_profile"}
    sized = size_manual(
        ctx.db,
        profile,
        engine_id=engine_id,
        server=str(opp["server"]),
        symbol=str(opp["symbol"]),
        side=Side(str(opp["side"])),
        entry=float(opp["entry"]),
        stop=float(opp["stop_loss"]),
        risk=load_app_config().risk,
        risk_percent=_risk_percent(ctx, user_id, None),
        now=ctx.clock.now_utc(),
        take_profit=opp.get("take_profit"),
        plan=PreferenceStore(ctx.db).get(user_id).entry_plan,
        atr=opp.get("atr"),
    )
    if sized.result is None or not sized.result.ok:
        return {"available": False, "reason": sized.reason}
    r = sized.result
    return {
        "available": True,
        "currency": profile.currency,
        "lot": float(r.volume),
        "risk_money": float(r.risk_money),
        "budget": float(r.budget),
        "taps": sum(p.taps for p in r.parts),
        "plan": list(plan_of(r)),
    }


class PreviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_plan: EntryPlanPreferences
    trading_profile: TradingProfile | None = None


@router.post("/engines/{engine_id}/entry-plan/preview")
async def entry_plan_preview(
    body: PreviewBody, engine: AdvisoryEngine, ctx: Context, session: CsrfSession
) -> dict[str, Any]:
    """A draft entry plan and trading profile sized on an example trade (TAA-922), before they are saved: the
    user's MANUAL account, or for the engine owner without one the engine's broker account from the latest
    ranking run (the account the owner's alerts are sized with)."""
    srv = await _server(ctx, engine.engine_id, None)

    def run() -> dict[str, Any]:
        profile = load_profile(ctx.db, session.user_id)
        if profile is None or profile.source != "MANUAL":
            account = reads(ctx).ranking(engine.engine_id, asset_class=None, eligible=None)["account"]
            if not engine.is_owner or not account or not account.get("equity") or not account.get("leverage"):
                return {"available": False, "reason": "no_account"}
            profile = AccountProfileRow(
                user_id=session.user_id,
                source="MANUAL",
                equity=float(account["equity"]),
                balance=float(account.get("balance") or account["equity"]),
                currency=str(account.get("currency") or "USD"),
                leverage=float(account["leverage"]),
                risk_percent=None,
            )
        prefs = PreferenceStore(ctx.db).get(session.user_id)
        trading = body.trading_profile or prefs.trading_profile
        pct = [load_app_config().risk.max_risk_per_trade_percent, trading.resolve().risk_per_signal_percent]
        if profile.risk_percent is not None:
            pct.append(profile.risk_percent)
        return preview_plan(
            ctx.db,
            profile,
            engine_id=engine.engine_id,
            server=srv,
            plan=body.entry_plan,
            risk=load_app_config().risk,
            risk_percent=min(pct),
            now=ctx.clock.now_utc(),
        )

    result: dict[str, Any] = await run_in_threadpool(run)
    return result


@router.get("/engines/{engine_id}/shadow-trades")
async def shadow_trades(
    engine: AdvisoryEngine,
    ctx: Context,
    status: Annotated[str | None, Query(pattern="^(OPEN|CLOSED|VOID)$")] = None,
    variant: Annotated[str | None, Query(pattern="^(PLAN|MANAGED)$")] = None,
    source: Annotated[str | None, Query(pattern="^(LIVE|REPLAY)$")] = None,
    symbol: Name = None,
    limit: Limit = None,
    cursor: Cursor = None,
) -> dict[str, Any]:
    page: Any = await _run(
        reads(ctx).shadow_trades,
        engine.engine_id,
        status=status,
        variant=variant,
        source=source,
        symbol=symbol,
        limit=limit,
        cursor=cursor,
    )
    out = dict(page.to_dict())
    if not engine.is_owner:
        out["items"] = [redact(i) for i in out["items"]]
    return out


Variant = Annotated[str, Query(pattern="^(PLAN|MANAGED)$")]
SourceQ = Annotated[str | None, Query(pattern="^(LIVE|REPLAY)$")]


@router.get("/engines/{engine_id}/accuracy")
async def accuracy(
    engine: AdvisoryEngine,
    ctx: Context,
    session: CurrentSession,
    server: Server = None,
    variant: Variant = "PLAN",
    since: datetime | None = None,
    mine: bool = False,
) -> dict[str, Any]:
    """The engine's whole record (owner), or only the alerts this user got at their own risk money (``mine``,
    always on the market feed)."""
    srv = await _server(ctx, engine.engine_id, server)
    if mine or not engine.is_owner:
        user_view: dict[str, Any] = await _run(
            reads(ctx).user_accuracy,
            engine.engine_id,
            srv,
            session.user_id,
            variant=variant,
            since=_aware(since),
        )
        return user_view
    prefs = await run_in_threadpool(_store(ctx).get, session.user_id)
    result: dict[str, Any] = await _run(
        reads(ctx).accuracy, engine.engine_id, srv, variant=variant, since=_aware(since), prefs=prefs
    )
    return result


@router.get("/engines/{engine_id}/threshold-explorer")
async def explorer(
    engine: AdvisoryEngine,
    ctx: Context,
    server: Server = None,
    variant: Variant = "PLAN",
    source: SourceQ = None,
    since: datetime | None = None,
) -> dict[str, Any]:
    srv = await _server(ctx, engine.engine_id, server)
    result: dict[str, Any] = await _run(
        reads(ctx).explorer,
        engine.engine_id,
        srv,
        variant=variant,
        source=source,
        since=_aware(since),
        money=engine.is_owner,
    )
    return result


@router.get("/engines/{engine_id}/theory-scoreboard")
async def theory_scoreboard(
    engine: AdvisoryEngine,
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
async def calibration(engine: AdvisoryEngine, ctx: Context, server: Server = None) -> dict[str, Any]:
    srv = await _server(ctx, engine.engine_id, server)
    found: dict[str, Any] | None = await _run(reads(ctx).calibration, engine.engine_id, srv)
    if found is None:
        raise ApiProblem(404, "calibration_not_found", "No calibration has been built yet")
    return found


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ApiProblem(400, "invalid_query", "since: a timezone-aware time is required")
    return value
