"""The AI review in the cloud: assessments, agreement and cost (PLAN §A15 "AI"; TAA-1304).

Reads the engine's replicated ``ai_assessments``. Agreement is measured against what the signal did
afterwards: the PLAN shadow trade of the same signal (``opportunity_id`` = the signal key). "The AI was right"
means it agreed and the trade won, or it disagreed and the trade lost. These are simulated outcomes, labelled
as such. The cloud never calls the AI: it holds no AI key (PLAN §A20).
"""

from __future__ import annotations

import random
from collections import Counter
from datetime import datetime, timedelta
from itertools import pairwise
from typing import Any

from sqlalchemy import func, select

from app.core.clock import Clock, ensure_utc
from app.storage.database import Database
from app.storage.models import AIAssessmentRow, AINoteRow, ShadowTradeRow
from app.web.readmodels import QueryError

MAX_DAYS = 366
MAX_ITEMS = 200
UNCOUNTED = ("BUDGET", "SKIPPED")


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


class AIReadModel:
    def __init__(self, db: Database, clock: Clock) -> None:
        self.db = db
        self.clock = clock

    def assessments(self, engine_id: str, *, days: int = 30, limit: int = 100) -> dict[str, Any]:
        if not 1 <= days <= MAX_DAYS:
            raise QueryError(f"days: 1-{MAX_DAYS}")
        limit = max(1, min(limit, MAX_ITEMS))
        now = self.clock.now_utc()
        since = now - timedelta(days=days)
        m = AIAssessmentRow
        with self.db.session() as sess:
            rows = list(
                sess.scalars(
                    select(m)
                    .where(m.engine_id == engine_id, m.created_at >= since)
                    .order_by(m.created_at.desc())
                )
            )
            keys = {r.signal_key for r in rows}
            shadows = {
                s.opportunity_id: s
                for s in sess.scalars(
                    select(ShadowTradeRow).where(
                        ShadowTradeRow.engine_id == engine_id,
                        ShadowTradeRow.opportunity_id.in_(keys),
                        ShadowTradeRow.variant == "PLAN",
                        ShadowTradeRow.status == "CLOSED",
                    )
                )
            }
        return {
            "days": days,
            "summary": self._summary(rows, shadows, now),
            "items": [self._item(r, shadows.get(r.signal_key)) for r in rows[:limit]],
        }

    @staticmethod
    def _item(r: AIAssessmentRow, shadow: ShadowTradeRow | None) -> dict[str, Any]:
        return {
            "assessment_id": r.assessment_id,
            "created_at": ensure_utc(r.created_at).isoformat(),
            "symbol": r.symbol,
            "strategy": r.strategy,
            "side": r.side,
            "mode": r.mode,
            "status": r.status,
            "verdict": r.verdict,
            "confidence": r.confidence,
            "reasons": list(r.reasons or []),
            "effect": r.effect,
            "model": r.model,
            "cost_usd": round(r.cost_usd, 6),
            "latency_ms": r.latency_ms,
            "outcome": None if shadow is None else {"win": shadow.win, "r": shadow.r_multiple},
        }

    @staticmethod
    def _summary(
        rows: list[AIAssessmentRow], shadows: dict[str, ShadowTradeRow], now: datetime
    ) -> dict[str, Any]:
        called = [r for r in rows if r.status not in UNCOUNTED]
        answered = [r for r in called if r.status == "OK" and r.verdict]
        verdicts = Counter(r.verdict for r in answered)
        effects = Counter(r.effect for r in rows)
        today = now.date()
        judged = [(r, shadows[r.signal_key]) for r in answered if r.signal_key in shadows]
        right = sum(
            1
            for r, s in judged
            if (r.verdict == "AGREE" and s.win is True) or (r.verdict == "DISAGREE" and s.win is False)
        )
        agree_outcomes = [s.win for r, s in judged if r.verdict == "AGREE" and s.win is not None]
        disagree_outcomes = [s.win for r, s in judged if r.verdict == "DISAGREE" and s.win is not None]
        latencies = [r.latency_ms for r in called if r.latency_ms is not None]
        return {
            "calls": len(called),
            "answered": len(answered),
            "unavailable": len(called) - len(answered),
            "budget_holds": sum(r.status == "BUDGET" for r in rows),
            "agree": verdicts.get("AGREE", 0),
            "disagree": verdicts.get("DISAGREE", 0),
            "unsure": verdicts.get("UNSURE", 0),
            "agreement_rate": _rate(verdicts.get("AGREE", 0), len(answered)),
            "vetoed": effects.get("VETOED", 0),
            "passed": effects.get("PASSED", 0),
            "advisory": effects.get("ADVISORY", 0),
            "with_outcome": len(judged),
            "right_rate": _rate(right, len(judged)),
            "win_rate_when_agree": _rate(sum(1 for w in agree_outcomes if w), len(agree_outcomes)),
            "win_rate_when_disagree": _rate(sum(1 for w in disagree_outcomes if w), len(disagree_outcomes)),
            "cost_usd": round(sum(r.cost_usd for r in called), 4),
            "cost_today_usd": round(
                sum(r.cost_usd for r in called if ensure_utc(r.created_at).date() == today), 4
            ),
            "tokens": sum(r.input_tokens + r.output_tokens for r in called),
            "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
            "models": sorted({r.model for r in called if r.model}),
        }


# --- AI notes on advisory (TAA-1305, TAA-1304) ---------------------------------------------------------

NOTE_KINDS = ("OPPORTUNITY", "RANKING", "ANALYTICS")
STATS_DAYS = 90  # the window of the opinion accuracy and of the alert filter's evaluation
FILTER_MIN_KEPT = 30  # the filter is offered only with at least this many judged AGREE opinions
FILTER_MIN_ALL = 50  # ... and this many judged opinions in all
BOOTSTRAP_RUNS = 1000
CALIBRATION_EDGES = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0000001)


def note_dict(r: AINoteRow) -> dict[str, Any]:
    return {
        "note_id": r.note_id,
        "kind": r.kind,
        "subject": r.subject,
        "created_at": ensure_utc(r.created_at).isoformat(),
        "status": r.status,
        "verdict": r.verdict,
        "confidence": r.confidence,
        "reasons": list(r.reasons or []),
        "text_en": r.text_en,
        "text_th": r.text_th,
        "model": r.model,
        "cost_usd": round(r.cost_usd, 6),
    }


def implied_win(verdict: str | None, confidence: int | None) -> float:
    """The win probability an opinion implies: AGREE at c percent is c, DISAGREE is 1 - c, UNSURE 0.5."""
    c = (confidence or 0) / 100
    if verdict == "AGREE":
        return c
    if verdict == "DISAGREE":
        return 1 - c
    return 0.5


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def opinion_stats(pairs: list[tuple[AINoteRow, ShadowTradeRow]]) -> dict[str, Any]:
    """Accuracy and calibration of answered opinions against their closed PLAN shadow trades (simulated)."""
    judged = [(n, s) for n, s in pairs if s.win is not None]
    by: dict[str, list[ShadowTradeRow]] = {"AGREE": [], "DISAGREE": [], "UNSURE": []}
    for n, s in judged:
        by.setdefault(n.verdict or "UNSURE", []).append(s)
    right = sum(
        1
        for n, s in judged
        if (n.verdict == "AGREE" and s.win) or (n.verdict == "DISAGREE" and s.win is False)
    )
    decided = sum(1 for n, _ in judged if n.verdict in ("AGREE", "DISAGREE"))
    wins = [1.0 if s.win else 0.0 for _, s in judged]
    base = _mean(wins)
    probs = [implied_win(n.verdict, n.confidence) for n, _ in judged]
    brier = _mean([(p - w) ** 2 for p, w in zip(probs, wins, strict=True)])
    brier_base = None if base is None else _mean([(base - w) ** 2 for w in wins])
    buckets = []
    for lo, hi in pairwise(CALIBRATION_EDGES):
        inside = [(p, w) for p, w in zip(probs, wins, strict=True) if lo <= p < hi]
        if inside:
            buckets.append(
                {
                    "low": round(lo, 2),
                    "high": round(min(hi, 1.0), 2),
                    "n": len(inside),
                    "implied": round(sum(p for p, _ in inside) / len(inside), 4),
                    "observed": round(sum(w for _, w in inside) / len(inside), 4),
                }
            )
    return {
        "judged": len(judged),
        "right_rate": _rate(right, decided),
        "base_win_rate": None if base is None else round(base, 4),
        "verdicts": {
            v: {
                "n": len(ts),
                "win_rate": _rate(sum(1 for t in ts if t.win), len(ts)),
                "avg_r": None if not ts else round(sum(t.r_multiple or 0.0 for t in ts) / len(ts), 4),
            }
            for v, ts in by.items()
        },
        "brier": None if brier is None else round(brier, 4),
        "brier_baseline": None if brier_base is None else round(brier_base, 4),
        "calibration": buckets,
        "simulated": True,
    }


def filter_evaluation(pairs: list[tuple[AINoteRow, ShadowTradeRow]], *, seed: int = 7) -> dict[str, Any]:
    """Would alerting only the opportunities the AI agrees with have done better? Mean R of the kept (AGREE)
    trades minus the mean R of all, with a bootstrap 95% interval. The filter is **offered** only with enough
    samples and an interval wholly above zero (TAA-1305: "offered only when it beats the baseline")."""
    rs = [(n.verdict == "AGREE", float(s.r_multiple)) for n, s in pairs if s.r_multiple is not None]
    kept = [r for agree, r in rs if agree]
    out: dict[str, Any] = {
        "n_all": len(rs),
        "n_kept": len(kept),
        "avg_r_all": None if not rs else round(sum(r for _, r in rs) / len(rs), 4),
        "avg_r_kept": None if not kept else round(sum(kept) / len(kept), 4),
        "diff": None,
        "ci_low": None,
        "ci_high": None,
        "min_kept": FILTER_MIN_KEPT,
        "min_all": FILTER_MIN_ALL,
        "offered": False,
    }
    if not kept:
        return out
    diff = sum(kept) / len(kept) - sum(r for _, r in rs) / len(rs)
    rng = random.Random(seed)  # noqa: S311  # nosec B311: a seeded bootstrap, not security
    diffs = []
    for _ in range(BOOTSTRAP_RUNS):
        sample = [rs[rng.randrange(len(rs))] for _ in rs]
        k = [r for agree, r in sample if agree]
        if k:
            diffs.append(sum(k) / len(k) - sum(r for _, r in sample) / len(sample))
    diffs.sort()
    low = diffs[int(0.025 * len(diffs))] if diffs else None
    high = diffs[min(len(diffs) - 1, int(0.975 * len(diffs)))] if diffs else None
    out.update(
        diff=round(diff, 4),
        ci_low=None if low is None else round(low, 4),
        ci_high=None if high is None else round(high, 4),
        offered=len(kept) >= FILTER_MIN_KEPT and len(rs) >= FILTER_MIN_ALL and low is not None and low > 0,
    )
    return out


class AINotesReadModel:
    def __init__(self, db: Database, clock: Clock) -> None:
        self.db = db
        self.clock = clock

    def note(self, engine_id: str, kind: str, subject: str) -> dict[str, Any] | None:
        with self.db.session() as sess:
            row = sess.get(AINoteRow, (engine_id, f"{kind}:{subject}"))
            return None if row is None else note_dict(row)

    def pairs(self, engine_id: str, since: datetime) -> list[tuple[AINoteRow, ShadowTradeRow]]:
        with self.db.session() as sess:
            notes = {
                n.subject: n
                for n in sess.scalars(
                    select(AINoteRow).where(
                        AINoteRow.engine_id == engine_id,
                        AINoteRow.kind == "OPPORTUNITY",
                        AINoteRow.status == "OK",
                        AINoteRow.created_at >= since,
                    )
                )
            }
            if not notes:
                return []
            shadows = sess.scalars(
                select(ShadowTradeRow).where(
                    ShadowTradeRow.engine_id == engine_id,
                    ShadowTradeRow.opportunity_id.in_(list(notes)),
                    ShadowTradeRow.variant == "PLAN",
                    ShadowTradeRow.status == "CLOSED",
                )
            )
            return [(notes[s.opportunity_id], s) for s in shadows]

    def filter_offered(self, engine_id: str) -> bool:
        since = self.clock.now_utc() - timedelta(days=STATS_DAYS)
        return bool(filter_evaluation(self.pairs(engine_id, since))["offered"])

    def notes(self, engine_id: str, *, kind: str, days: int = 30, limit: int = 50) -> dict[str, Any]:
        if kind not in NOTE_KINDS:
            raise QueryError(f"kind: one of {', '.join(NOTE_KINDS)}")
        if not 1 <= days <= MAX_DAYS:
            raise QueryError(f"days: 1-{MAX_DAYS}")
        limit = max(1, min(limit, MAX_ITEMS))
        now = self.clock.now_utc()
        since = now - timedelta(days=days)
        with self.db.session() as sess:
            rows = list(
                sess.scalars(
                    select(AINoteRow)
                    .where(
                        AINoteRow.engine_id == engine_id,
                        AINoteRow.kind == kind,
                        AINoteRow.created_at >= since,
                    )
                    .order_by(AINoteRow.created_at.desc())
                    .limit(limit)
                )
            )
            cost = sess.scalar(
                select(func.coalesce(func.sum(AINoteRow.cost_usd), 0.0)).where(
                    AINoteRow.engine_id == engine_id, AINoteRow.created_at >= since
                )
            )
        out: dict[str, Any] = {
            "kind": kind,
            "days": days,
            "cost_usd": round(float(cost or 0.0), 4),
            "items": [note_dict(r) for r in rows],
            "stats": None,
            "filter": None,
        }
        if kind == "OPPORTUNITY":
            pairs = self.pairs(engine_id, now - timedelta(days=STATS_DAYS))
            out["stats"] = opinion_stats(pairs)
            out["filter"] = filter_evaluation(pairs)
        return out
