"""AI on advisory (PLAN §A26 "AI", R21; TAA-1305, TAA-1304): opinions on opportunities and narratives.

Three kinds of note, all written on the engine (the cloud holds no AI key, PLAN §A20) and replicated as
``ai_notes`` rows:

- ``OPPORTUNITY``: an opinion on one market opportunity: a verdict AGREE / DISAGREE / UNSURE with a confidence
  and up to five factual reasons, plus a short TH and EN narrative of what the facts show. It is recorded so
  its accuracy can be measured against the opportunity's shadow outcome (:mod:`app.web.ai`).
- ``RANKING``: a TH/EN narrative of one ranking snapshot (which symbols lead and why, by the score's parts).
- ``ANALYTICS``: a TH/EN narrative of the engine's recent shadow results.

The AI is **descriptive only**: it never changes a score, a probability, an alert or a trade. Inputs are
numeric facts and engine-made codes, never account data or free text from outside (§A20 "prompt injection").
Answers are strict schemas that echo the subject they describe, and a text that claims profit or certainty
is refused (:data:`CLAIMS`), like the UI catalogs (no profitability claims anywhere).
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.ai.schema import MAX_REASON_CHARS, MAX_REASONS, SCHEMA_VERSION, Verdict
from app.core.clock import ensure_utc
from app.storage.models import OpportunityRow, ShadowTradeRow, SuitabilitySnapshotRow

MAX_NARRATIVE_CHARS = 700
MAX_SUMMARY_CHARS = 1400


class Kind(StrEnum):
    OPPORTUNITY = "OPPORTUNITY"
    RANKING = "RANKING"
    ANALYTICS = "ANALYTICS"


# a narrative must describe, never promise: refused when it claims profit or certainty (EN and TH)
CLAIMS = re.compile(
    r"guarantee|risk[- ]free|sure (?:win|profit|thing)|will (?:surely )?(?:profit|win|make money)|"
    r"easy money|can'?t lose|cannot lose|การันตี|รับประกัน|ไม่มีความเสี่ยง|กำไรแน่|ได้กำไรแน่นอน|ชนะแน่",
    re.IGNORECASE,
)


class OpinionV1(BaseModel):
    """The model's opinion on one opportunity. ``subject`` must repeat the input's, verbatim."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"]
    subject: str = Field(min_length=1, max_length=120)
    verdict: Verdict
    confidence: int = Field(ge=0, le=100, description="0-100: how sure the verdict is")
    reasons: list[str] = Field(max_length=MAX_REASONS, description="short, factual, from the input only")
    narrative_en: str = Field(max_length=MAX_NARRATIVE_CHARS, description="2-4 sentences, descriptive")
    narrative_th: str = Field(max_length=MAX_NARRATIVE_CHARS, description="the same in Thai")


class NarrativeV1(BaseModel):
    """A narrative of a ranking snapshot or of recent results. ``subject`` must repeat the input's."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"]
    subject: str = Field(min_length=1, max_length=120)
    text_en: str = Field(max_length=MAX_SUMMARY_CHARS, description="3-6 sentences, descriptive")
    text_th: str = Field(max_length=MAX_SUMMARY_CHARS, description="the same in Thai")


_COMMON = (
    "The input is a JSON object of numeric facts and engine-made codes from an automated market scanner. "
    "Judge only from these facts. Be descriptive and neutral: describe what the facts show, never "
    "recommend buying or selling, never promise or imply a profit, never claim certainty, and never "
    "mention money amounts or the account. Write the Thai text in natural Thai, not a word-for-word "
    "translation. Repeat subject exactly as given and set schema_version to 1.0."
)

OPINION_PROMPT = (
    "You give a second opinion on one market opportunity found by the scanner: a strategy's entry signal "
    "with its entry, stop-loss and take-profit, reward-to-risk, setup strength, score, the session, the "
    "regime, the ATR, the spread, the checklist conditions, the evidence families that support or oppose "
    "it (signed, -1..1) and the confluence by family. Answer AGREE when the facts are consistent with the "
    "signal, DISAGREE when they argue against it (for example opposing higher-timeframe trend evidence, a "
    "stop inside noise, a target unrealistic for the volatility, or a large spread against the stop), and "
    "UNSURE when they are mixed. Confidence is 0-100. Give at most five short reasons that cite the input. "
    "narrative_en and narrative_th: two to four sentences each on what the facts show. " + _COMMON
)

RANKING_PROMPT = (
    "You describe one snapshot of the scanner's symbol ranking: for each listed symbol its rank, asset "
    "class, overall and current scores, whether it is eligible and which gates it failed, plus counts for "
    "the whole universe. In three to six sentences per language, say which symbols lead and what their "
    "scores have in common, which gates hold most symbols back, and anything unusual. " + _COMMON
)

ANALYTICS_PROMPT = (
    "You describe the recent results of the scanner's hypothetical (shadow) trades: counts, win share, "
    "average R overall and per strategy, per asset class and per session, over the stated period. These "
    "are simulated outcomes. In three to six sentences per language, say what stands out (strong and weak "
    "groups, small samples that should not be trusted yet) without predicting the future. " + _COMMON
)


@dataclass(frozen=True, slots=True)
class NoteRequest:
    kind: Kind
    subject: str  # the note's key within its kind; the answer must echo it
    payload: dict[str, Any]

    @property
    def note_id(self) -> str:
        return f"{self.kind.value}:{self.subject}"

    def to_json(self) -> str:
        return json.dumps(self.payload, sort_keys=True, separators=(",", ":"))

    @property
    def prompt(self) -> str:
        return {Kind.OPPORTUNITY: OPINION_PROMPT, Kind.RANKING: RANKING_PROMPT}.get(
            self.kind, ANALYTICS_PROMPT
        )

    @property
    def schema(self) -> type[BaseModel]:
        return OpinionV1 if self.kind is Kind.OPPORTUNITY else NarrativeV1


def _num(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return round(f, digits) if math.isfinite(f) else None


# inputs ----------------------------------------------------------------------------------------------------


def opinion_request(row: OpportunityRow) -> NoteRequest:
    """The numeric facts of one opportunity (no lot, money, equity or account)."""
    signal = row.signal or {}
    conditions = [
        {"name": str(c.get("name", ""))[:40], "passed": bool(c.get("passed"))}
        for c in signal.get("conditions", [])
        if isinstance(c, dict)
    ][:20]
    features = {str(k)[:80]: _num(v, 4) for k, v in sorted((row.features or {}).items())[:60]}
    confluence = [
        [str(item[0])[:24], _num(item[1], 3)]
        for item in signal.get("confluence", [])
        if isinstance(item, (list, tuple)) and len(item) == 2
    ][:12]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "subject": row.opportunity_id,
        "bar_close_utc": ensure_utc(row.bar_close_at).isoformat(),
        "symbol": row.symbol,
        "asset_class": row.asset_class,
        "timeframe": row.timeframe,
        "side": row.side,
        "strategy": row.strategy,
        "entry": _num(row.entry),
        "stop_loss": _num(row.stop_loss),
        "take_profit": _num(row.take_profit),
        "reward_to_risk": _num(row.rr, 3),
        "setup_strength": _num(row.setup_strength, 2),
        "score": _num(row.score, 2),
        "session": row.session,
        "regime": row.regime,
        "atr": _num(row.atr),
        "spread_points": _num(row.spread_points, 1),
        "reason_codes": [str(c)[:40] for c in signal.get("reason_codes", [])][:20],
        "warnings": [str(w)[:40] for w in (row.warnings or [])][:10],
        "conditions": conditions,
        "evidence": features,
        "confluence": confluence,
    }
    return NoteRequest(Kind.OPPORTUNITY, row.opportunity_id, payload)


def ranking_request(rows: Sequence[SuitabilitySnapshotRow], top: int = 12) -> NoteRequest | None:
    """One snapshot hour: the top *top* symbols by rank, and how many fail each gate."""
    if not rows:
        return None
    hour = ensure_utc(max(r.hour for r in rows))
    current = sorted((r for r in rows if ensure_utc(r.hour) == hour), key=lambda r: r.rank)
    gates: dict[str, int] = {}
    for r in current:
        for g in r.failed_gates or []:
            gates[str(g)[:40]] = gates.get(str(g)[:40], 0) + 1
    subject = hour.isoformat()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "subject": subject,
        "symbols": len(current),
        "eligible": sum(1 for r in current if r.eligible),
        "failed_gates": dict(sorted(gates.items(), key=lambda kv: -kv[1])[:10]),
        "top": [
            {
                "rank": r.rank,
                "symbol": r.symbol,
                "asset_class": r.asset_class,
                "eligible": r.eligible,
                "overall": _num(r.overall, 2),
                "now_score": _num(r.now_score, 2),
                "failed_gates": [str(g)[:40] for g in (r.failed_gates or [])][:5],
            }
            for r in current[:top]
        ],
    }
    return NoteRequest(Kind.RANKING, subject, payload)


def _group(trades: Iterable[ShadowTradeRow], key: str) -> list[dict[str, Any]]:
    groups: dict[str, list[float]] = {}
    wins: dict[str, int] = {}
    for t in trades:
        name = str(getattr(t, key))
        groups.setdefault(name, []).append(float(t.r_multiple or 0.0))
        wins[name] = wins.get(name, 0) + (1 if t.win else 0)
    out = [
        {
            "name": k,
            "trades": len(v),
            "win_share": _num(wins[k] / len(v), 3),
            "avg_r": _num(sum(v) / len(v), 3),
        }
        for k, v in groups.items()
    ]
    return sorted(out, key=lambda g: -len(groups[str(g["name"])]))[:10]


def analytics_request(
    trades: Sequence[ShadowTradeRow], since: datetime, until: datetime
) -> NoteRequest | None:
    """Closed PLAN shadow trades of the period, overall and per strategy, asset class and session."""
    closed = [t for t in trades if t.status == "CLOSED" and t.r_multiple is not None]
    if not closed:
        return None
    rs = [float(t.r_multiple or 0.0) for t in closed]
    subject = f"{ensure_utc(since).date().isoformat()}/{ensure_utc(until).date().isoformat()}"
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "subject": subject,
        "simulated": True,
        "period_days": max(1, (ensure_utc(until) - ensure_utc(since)).days),
        "trades": len(closed),
        "win_share": _num(sum(1 for t in closed if t.win) / len(closed), 3),
        "avg_r": _num(sum(rs) / len(rs), 3),
        "by_strategy": _group(closed, "strategy"),
        "by_asset_class": _group(closed, "asset_class"),
        "by_session": _group(closed, "session"),
    }
    return NoteRequest(Kind.ANALYTICS, subject, payload)


# answers ---------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Checked:
    verdict: Verdict | None
    confidence: int | None
    reasons: tuple[str, ...]
    text_en: str
    text_th: str


def _clean(text: str, limit: int) -> str:
    return " ".join(text.split())[:limit]


def check(raw: Any, request: NoteRequest) -> Checked:
    """Parse and check an answer: the schema, the echoed subject and the claim filter.

    Raises ``ValueError``."""
    schema = request.schema
    try:
        answer = raw if isinstance(raw, schema) else schema.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"the answer does not match {schema.__name__}: {exc.error_count()} errors") from exc
    if getattr(answer, "subject", None) != request.subject:
        raise ValueError(
            f"the answer describes {getattr(answer, 'subject', None)!r}, not {request.subject!r}"
        )
    if isinstance(answer, OpinionV1):
        reasons = tuple(_clean(r, MAX_REASON_CHARS) for r in answer.reasons if r.strip())
        result = Checked(
            answer.verdict,
            answer.confidence,
            reasons,
            _clean(answer.narrative_en, MAX_NARRATIVE_CHARS),
            _clean(answer.narrative_th, MAX_NARRATIVE_CHARS),
        )
    elif isinstance(answer, NarrativeV1):
        result = Checked(
            None,
            None,
            (),
            _clean(answer.text_en, MAX_SUMMARY_CHARS),
            _clean(answer.text_th, MAX_SUMMARY_CHARS),
        )
    else:  # pragma: no cover - request.schema is one of the two
        raise ValueError(f"unexpected answer type {type(answer).__name__}")
    for text in (result.text_en, result.text_th, *result.reasons):
        if CLAIMS.search(text):
            raise ValueError("the answer claims profit or certainty")
    if not result.text_en or not result.text_th:
        raise ValueError("the answer has an empty narrative")
    return result
