"""Calibration and evidence-model builder (PLAN §A27 "Calibration", §A29; TAA-6C3).

**Training rows:** CLOSED shadow trades of the ``PLAN`` variant (the "as planned" result), LIVE and REPLAY,
as :class:`~app.advisory.confidence.Outcome` rows: win = TP first; a time stop or any stop-out is a loss
(hit rate = TP first ÷ resolved, §A27). VOID trades and rows without a planned RR are skipped.

**Build** (:func:`build`):

- the bucket model (strategy × symbol × strength bucket × RR band, pooled by empirical Bayes toward
  strategy × asset class × RR band → strategy × RR band → the random baseline), REPLAY as a capped prior;
- the evidence model per strategy × asset class (pooled fallback), REPLAY down-weighted, chosen only when
  walk-forward CV beats the bucket model (:func:`~app.advisory.confidence.build_win_probability`);
- the Brier score and reliability bins of the selected model from the walk-forward (out-of-sample)
  predictions.

**Versions:** :func:`save` writes one ``calibration_tables`` row and its ``evidence_model_versions`` rows
under a version ``<UTC timestamp>-<content hash>`` and keeps the newest ``keep_versions``; :func:`load_latest`
rebuilds the :class:`~app.advisory.confidence.WinProbability` from them. Opportunities record the version
they were scored with.

**Schedule** (:class:`CalibrationService`): once a day after ``nightly_hour_utc`` (and at the first start
without a version), or on demand (:meth:`CalibrationService.request_rebuild`, ``app.cli advisory
calibrate``). The engine runs a rebuild on a worker thread so the trading loop never waits for it.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from collections.abc import Callable, Hashable, Iterable, Sequence
from concurrent.futures import Executor, Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from sqlalchemy import delete, select

from app.advisory.confidence import (
    BucketModel,
    CVReport,
    EvidenceModelSet,
    LogisticModel,
    Outcome,
    Source,
    WinProbability,
    build_win_probability,
    walk_forward,
)
from app.advisory.shadow import ShadowStatus, Variant
from app.config import CalibrationConfig
from app.core.clock import Clock, ensure_utc
from app.core.errors import TaaError
from app.storage.database import Database
from app.storage.models import CalibrationTableRow, EvidenceModelVersionRow, ShadowTradeRow
from app.storage.models.base import LOCAL_ENGINE

log = logging.getLogger(__name__)


# --- training rows ------------------------------------------------------------------------------------------


def outcome_of(row: ShadowTradeRow) -> Outcome | None:
    """A CLOSED shadow row as a training outcome; None when it cannot train (open, void, no RR)."""
    if row.status != ShadowStatus.CLOSED.value or row.rr is None or row.win is None:
        return None
    return Outcome(
        strategy=row.strategy,
        symbol=row.symbol,
        asset_class=row.asset_class,
        strength=row.setup_strength,
        rr=row.rr,
        win=bool(row.win),
        source=Source(row.source),
        features=dict(row.features),
        at=ensure_utc(row.signal_at),
        timeframe=row.timeframe,
    )


def outcomes_from_shadows(
    db: Database, *, server: str, variant: Variant = Variant.PLAN, since: datetime | None = None
) -> list[Outcome]:
    query = select(ShadowTradeRow).where(
        ShadowTradeRow.server == server,
        ShadowTradeRow.variant == variant.value,
        ShadowTradeRow.status == ShadowStatus.CLOSED.value,
    )
    if since is not None:
        query = query.where(ShadowTradeRow.signal_at >= since)
    with db.session() as sess:
        rows = list(
            sess.execute(query.order_by(ShadowTradeRow.signal_at, ShadowTradeRow.shadow_id)).scalars()
        )
    return [o for o in (outcome_of(r) for r in rows) if o is not None]


# --- reliability --------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReliabilityBin:
    low: float  # predicted probability range, [low, high)
    high: float
    n: int
    mean_predicted: float | None
    observed: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "low": self.low,
            "high": self.high,
            "n": self.n,
            "mean_predicted": self.mean_predicted,
            "observed": self.observed,
        }


def reliability(
    predicted: Sequence[float], outcomes: Sequence[float], bins: int = 10
) -> list[ReliabilityBin]:
    """Predicted vs observed win rate per equal-width probability bin (probabilities in [0, 1])."""
    p = np.clip(np.asarray(predicted, dtype=float), 0.0, 1.0)
    y = np.asarray(outcomes, dtype=float)
    index = np.minimum((p * bins).astype(int), bins - 1)
    out = []
    for k in range(bins):
        mask = index == k
        n = int(mask.sum())
        out.append(
            ReliabilityBin(
                k / bins,
                (k + 1) / bins,
                n,
                float(p[mask].mean()) if n else None,
                float(y[mask].mean()) if n else None,
            )
        )
    return out


# --- build --------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CalibrationBuild:
    version: str
    server: str
    built_at: datetime
    variant: Variant
    model: WinProbability
    report: CVReport | None  # walk-forward verdict (also run without features, for reliability)
    n_live: int
    n_replay: int
    window: tuple[datetime | None, datetime | None]
    brier: float | None  # selected model, out of sample
    reliability: tuple[ReliabilityBin, ...]
    params: dict[str, Any]


def _finite(value: float) -> float | None:
    return value if math.isfinite(value) else None


def build(
    outcomes: Sequence[Outcome],
    cfg: CalibrationConfig,
    *,
    server: str,
    built_at: datetime,
    variant: Variant = Variant.PLAN,
) -> CalibrationBuild:
    model = build_win_probability(
        outcomes,
        kappa=cfg.kappa,
        min_trades=cfg.min_trades,
        replay_cap=cfg.replay_cap,
        folds=cfg.folds,
        l2=cfg.l2,
        min_group=cfg.min_group,
        margin=cfg.min_brier_improvement,
    )
    report = model.report
    if report is None and outcomes:  # no features: still measure the bucket model out of sample
        report = walk_forward(
            outcomes,
            folds=cfg.folds,
            bucket=lambda: BucketModel(kappa=cfg.kappa, min_trades=cfg.min_trades, replay_cap=cfg.replay_cap),
            l2=cfg.l2,
            min_group=cfg.min_group,
            margin=cfg.min_brier_improvement,
        )
    preds = report.predictions if report is not None else ()
    pick = 1 if model.uses_evidence else 0
    chosen = [row[pick] for row in preds]
    ys = [row[2] for row in preds]
    brier_value = None
    if report is not None and report.n_test:
        brier_value = _finite(report.brier_evidence if model.uses_evidence else report.brier_bucket)
    times = [o.at for o in outcomes if o.at is not None]
    params = {
        "kappa": cfg.kappa,
        "min_trades": cfg.min_trades,
        "replay_cap": cfg.replay_cap,
        "replay_weight": cfg.replay_weight,
        "folds": cfg.folds,
        "l2": cfg.l2,
        "min_group": cfg.min_group,
        "min_brier_improvement": cfg.min_brier_improvement,
    }
    cells = _cells(model.bucket)
    digest = hashlib.sha256(
        json.dumps({"cells": cells, "params": params, "n": len(outcomes)}, sort_keys=True).encode()
    ).hexdigest()[:12]
    return CalibrationBuild(
        version=f"{ensure_utc(built_at):%Y%m%dT%H%M%SZ}-{digest}",
        server=server,
        built_at=ensure_utc(built_at),
        variant=variant,
        model=model,
        report=report,
        n_live=sum(1 for o in outcomes if o.source is Source.LIVE),
        n_replay=sum(1 for o in outcomes if o.source is Source.REPLAY),
        window=(min(times) if times else None, max(times) if times else None),
        brier=brier_value,
        reliability=tuple(reliability(chosen, ys, cfg.reliability_bins)),
        params=params,
    )


# --- persistence --------------------------------------------------------------------------------------------


def _cells(bucket: BucketModel) -> list[list[Any]]:
    return sorted(
        [list(key), c.live_wins, c.live_n, c.replay_wins, c.replay_n] for key, c in bucket.cells.items()
    )


def _cv_dict(report: CVReport | None) -> dict[str, Any]:
    if report is None:
        return {}
    return {
        "folds": report.folds,
        "n_test": report.n_test,
        "brier_bucket": _finite(report.brier_bucket),
        "brier_evidence": _finite(report.brier_evidence),
        "log_loss_bucket": _finite(report.log_loss_bucket),
        "log_loss_evidence": _finite(report.log_loss_evidence),
        "margin": report.margin,
    }


def _model_row(b: CalibrationBuild, model: LogisticModel, key: Hashable | None) -> EvidenceModelVersionRow:
    group = [] if key is None else [str(k) for k in key] if isinstance(key, tuple) else [str(key)]
    return EvidenceModelVersionRow(
        version=b.version,
        server=b.server,
        built_at=b.built_at,
        pooled=key is None,
        group_key=group,
        names=list(model.names),
        coef=[float(v) for v in model.coef],
        intercept=float(model.intercept),
        means=[float(v) for v in model.means],
        active=[] if model.active is None else [float(v) for v in model.active],
        l2=float(model.l2),
        n=int(model.n),
    )


def save(db: Database, b: CalibrationBuild, *, keep: int = 30) -> str:
    """Store a build (idempotent per version) and drop versions beyond the newest *keep* of this server."""
    with db.session() as sess:
        if sess.get(CalibrationTableRow, (LOCAL_ENGINE, b.version)) is None:
            sess.add(
                CalibrationTableRow(
                    version=b.version,
                    server=b.server,
                    built_at=b.built_at,
                    variant=b.variant.value,
                    n_live=b.n_live,
                    n_replay=b.n_replay,
                    window_start=b.window[0],
                    window_end=b.window[1],
                    params=dict(b.params),
                    cells=_cells(b.model.bucket),
                    cv=_cv_dict(b.report),
                    uses_evidence=b.model.uses_evidence,
                    brier=b.brier,
                    reliability=[r.to_dict() for r in b.reliability],
                )
            )
            evidence = b.model.evidence if b.model.uses_evidence else None
            if evidence is not None:
                for key, model in sorted(evidence.models.items(), key=lambda kv: str(kv[0])):
                    sess.add(_model_row(b, model, key))
                if evidence.pooled is not None:
                    sess.add(_model_row(b, evidence.pooled, None))
    _prune(db, b.server, keep)
    return b.version


def _prune(db: Database, server: str, keep: int) -> None:
    with db.session() as sess:
        versions = list(
            sess.execute(
                select(CalibrationTableRow.version)
                .where(CalibrationTableRow.server == server)
                .order_by(CalibrationTableRow.built_at.desc(), CalibrationTableRow.version.desc())
            ).scalars()
        )
        old = versions[keep:]
        if old:
            sess.execute(delete(EvidenceModelVersionRow).where(EvidenceModelVersionRow.version.in_(old)))
            sess.execute(delete(CalibrationTableRow).where(CalibrationTableRow.version.in_(old)))


@dataclass(frozen=True)
class LoadedCalibration:
    version: str
    built_at: datetime
    model: WinProbability
    n_live: int
    n_replay: int


def _logistic(row: EvidenceModelVersionRow) -> LogisticModel:
    return LogisticModel(
        tuple(row.names),
        np.asarray(row.coef, dtype=float),
        row.intercept,
        np.asarray(row.means, dtype=float),
        row.l2,
        row.n,
        np.asarray(row.active, dtype=float) if row.active else None,
    )


def _nan(value: Any) -> float:
    return math.nan if value is None else float(value)


def load_version(db: Database, version: str, engine_id: str = LOCAL_ENGINE) -> LoadedCalibration:
    with db.session() as sess:
        row = sess.get(CalibrationTableRow, (engine_id, version))
        if row is None:
            raise TaaError(f"calibration version {version} not found")
        models = list(
            sess.execute(
                select(EvidenceModelVersionRow)
                .where(
                    EvidenceModelVersionRow.engine_id == engine_id, EvidenceModelVersionRow.version == version
                )
                .order_by(EvidenceModelVersionRow.id)
            ).scalars()
        )
    params = row.params
    bucket = BucketModel(
        kappa=params["kappa"], min_trades=params["min_trades"], replay_cap=params["replay_cap"]
    )
    for key, live_wins, live_n, replay_wins, replay_n in row.cells:
        cell = bucket.cells[tuple(key)]
        cell.live_wins, cell.live_n, cell.replay_wins, cell.replay_n = (
            live_wins,
            live_n,
            replay_wins,
            replay_n,
        )
    cv = row.cv
    report = None
    if cv:
        report = CVReport(
            cv["folds"],
            cv["n_test"],
            _nan(cv["brier_bucket"]),
            _nan(cv["brier_evidence"]),
            _nan(cv["log_loss_bucket"]),
            _nan(cv["log_loss_evidence"]),
            float(cv.get("margin", 0.0)),
        )
    evidence = None
    if row.uses_evidence and models:
        evidence = EvidenceModelSet(
            {tuple(m.group_key): _logistic(m) for m in models if not m.pooled},
            next((_logistic(m) for m in models if m.pooled), None),
        )
    model = WinProbability(bucket, evidence, report)
    return LoadedCalibration(row.version, ensure_utc(row.built_at), model, row.n_live, row.n_replay)


def latest_version(db: Database, server: str, engine_id: str = LOCAL_ENGINE) -> tuple[str, datetime] | None:
    with db.session() as sess:
        row = sess.execute(
            select(CalibrationTableRow.version, CalibrationTableRow.built_at)
            .where(CalibrationTableRow.engine_id == engine_id, CalibrationTableRow.server == server)
            .order_by(CalibrationTableRow.built_at.desc(), CalibrationTableRow.version.desc())
            .limit(1)
        ).first()
    return None if row is None else (row[0], ensure_utc(row[1]))


def load_latest(db: Database, server: str, engine_id: str = LOCAL_ENGINE) -> LoadedCalibration | None:
    latest = latest_version(db, server, engine_id)
    return None if latest is None else load_version(db, latest[0], engine_id)


# --- schedule -----------------------------------------------------------------------------------------------


def next_nightly(after: datetime, hour_utc: int) -> datetime:
    """The first ``hour_utc``:00 UTC strictly after *after*."""
    after = ensure_utc(after)
    candidate = after.replace(hour=hour_utc, minute=0, second=0, microsecond=0)
    return candidate if candidate > after else candidate + timedelta(days=1)


class _Inline(Executor):
    """Runs submitted work immediately (tests and the CLI)."""

    def submit(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Future[Any]:
        future: Future[Any] = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except Exception as exc:  # delivered through the future, like a worker thread would
            future.set_exception(exc)
        return future


class CalibrationService:
    RETRY_SECONDS = 3600.0

    def __init__(
        self,
        db: Database,
        cfg: CalibrationConfig,
        clock: Clock,
        *,
        server: str,
        executor: Executor | None = None,
        outcomes: Callable[[], Iterable[Outcome]] | None = None,
    ) -> None:
        self.db = db
        self.cfg = cfg
        self.clock = clock
        self.server = server
        self.executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix="calibration")
        self.outcomes = outcomes or (lambda: outcomes_from_shadows(db, server=server))
        self.current: LoadedCalibration | None = None
        self.builds = 0
        self.failures = 0
        self.last_error = ""
        self._requested = False
        self._running: Future[LoadedCalibration] | None = None
        self._retry_at = 0.0

    @staticmethod
    def inline() -> Executor:
        return _Inline()

    def load(self) -> LoadedCalibration | None:
        self.current = load_latest(self.db, self.server)
        return self.current

    def request_rebuild(self) -> None:
        self._requested = True

    def due(self, now: datetime) -> bool:
        if self._requested:
            return True
        latest = latest_version(self.db, self.server)
        return latest is None or now >= next_nightly(latest[1], self.cfg.nightly_hour_utc)

    def rebuild(self) -> LoadedCalibration:
        """Build from every PLAN shadow outcome, save it and return the loaded version (synchronous)."""
        now = self.clock.now_utc()
        b = build(list(self.outcomes()), self.cfg, server=self.server, built_at=now)
        save(self.db, b, keep=self.cfg.keep_versions)
        log.info(
            "calibration %s: %d live + %d replay outcomes, evidence model %s, Brier %s",
            b.version,
            b.n_live,
            b.n_replay,
            "used" if b.model.uses_evidence else "not used",
            "n/a" if b.brier is None else f"{b.brier:.4f}",
        )
        return load_version(self.db, b.version)

    def tick(self) -> LoadedCalibration | None:
        """Collect a finished rebuild, then start one when due. Returns the newly loaded version, if any.

        A failed build keeps the previous version and is retried after ``RETRY_SECONDS``.
        """
        loaded = self._collect()
        now = self.clock.monotonic()
        if self._running is None and now >= self._retry_at and self.due(self.clock.now_utc()):
            self._requested = False
            self._running = self.executor.submit(self.rebuild)
            loaded = self._collect() or loaded  # an inline executor has finished already
        return loaded

    def _collect(self) -> LoadedCalibration | None:
        if self._running is None or not self._running.done():
            return None
        future, self._running = self._running, None
        try:
            loaded = future.result()
        except Exception as exc:  # advisory boundary: a failed build keeps the previous version
            log.error("calibration rebuild failed: %s", exc, exc_info=exc)
            self.failures += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            self._retry_at = self.clock.monotonic() + self.RETRY_SECONDS
            return None
        self.current = loaded
        self.builds += 1
        return loaded

    def shutdown(self) -> None:
        """Cancel a queued build and wait for a running one, so no thread touches a closed database."""
        self.executor.shutdown(wait=True, cancel_futures=True)
