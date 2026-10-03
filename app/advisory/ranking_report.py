"""Plain-text table of a ranking run (``python -m app.cli advisory rank``)."""

from __future__ import annotations

from app.advisory.explanations import Language, explain
from app.advisory.market_sessions import describe_hour
from app.advisory.ranking_service import RankingRun, failed_reasons

DISCLAIMER = {
    "en": "Advisory only: suitability for this account's size and costs; not a forecast or trading advice.",
    "th": "ข้อมูลประกอบการตัดสินใจเท่านั้น: วัดความเหมาะสมกับขนาดบัญชีและต้นทุน ไม่ใช่การคาดการณ์หรือคำแนะนำให้เทรด",
}


def _money(value: object) -> str:
    return "-" if value is None else f"{float(value):,.2f}"  # type: ignore[arg-type]


def format_ranking(run: RankingRun, *, top: int | None = None, language: Language = "en") -> str:
    header = (
        f"{'#':>3}  {'Symbol':10} {'Class':13} {'OK':3} {'Now':>5} {'Overall':>7} {'Lot':>6} "
        f"{'MinLotRisk':>10} {'NeedsEquity':>12} {'Session':8} Note"
    )
    lines = [
        f"Suitability ranking {run.computed_at:%Y-%m-%d %H:%M} UTC, account currency {run.currency}, "
        f"{sum(r.eligible for r in run.ranked)} of {len(run.ranked)} eligible",
        header,
        "-" * len(header),
    ]
    for r in run.ranked[:top] if top else run.ranked:
        s = r.suitability
        session = run.sessions.get(r.symbol)
        state = "-" if session is None else ("open" if session.open else "closed")
        if r.eligible:
            hours = run.best_hours.get(r.symbol, [])
            note = "best: " + ", ".join(describe_hour(h) for h in hours) if hours else ""
        else:
            reasons = failed_reasons(r)
            note = explain(*reasons[0], language) if reasons else "not evaluated"
        lines.append(
            f"{r.rank:>3}  {r.symbol:10} {s.asset_class.value:13} {'yes' if r.eligible else 'no':3} "
            f"{r.now:>5.1f} {r.overall:>7.1f} {('-' if s.lot is None else f'{s.lot}'):>6} "
            f"{_money(s.min_lot_risk):>10} {_money(s.required_equity):>12} {state:8} {note}"
        )
    lines.append("")
    lines.append(DISCLAIMER[language])
    return "\n".join(lines)
