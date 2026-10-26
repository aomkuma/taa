"""TAA-1807 parity: the live shadow's decisions of 2026-10-23 re-created through the replay's entry point.

For every stored answer (ai/raw/*_3_answer.json) the replay's bars at that minute (app.engine.ai_replay.HistoryCandles
over the history store, the AI lane's own frame builder) go through app.ai.trader.decide with the stored answer pinned
as the provider's reply. Checked per call:
- the prompt's sections built from bars and knowledge (NOW, READINGS, KNOWLEDGE, DAY'S LEVELS, READERS) byte-equal
  to the prompt the live shadow sent (the journal sections are inputs, not bars: not compared);
- the brakes' result (final size, vetoes) equal to the stored one.

    .venv/Scripts/python research/2026-10-23-entry/parity_replay.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from app.ai import trader  # noqa: E402
from app.ai.providers import Answer  # noqa: E402
from app.ai.schema import Status  # noqa: E402
from app.config import AITraderConfig  # noqa: E402
from app.core.clock import ManualClock  # noqa: E402
from app.engine.ai_replay import HistoryCandles  # noqa: E402
from app.engine.ai_trader import COUNTS, AITraderLane  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402
from app.news.releases import load_releases  # noqa: E402
from app.strategy import knowledge as kn  # noqa: E402

AI = HERE / "ai"
SECTIONS = ("NOW:", "READINGS", "WHAT THE KNOWLEDGE BASE", "SUSPENDED BY", "THE DAY'S OWN LEVELS", "THE READERS' OUTPUT")


class Pinned:
    """Replies with the stored answer."""

    name = "pinned"

    def __init__(self, decision: dict) -> None:
        self.decision = decision

    def ask(self, key, system, content, output_format, **kw) -> Answer:  # noqa: ANN001
        d = {"watch_above": None, "watch_below": None, "weapon": "none", "buy_side": "-", "sell_side": "-", "buy_odds": 0,
             "sell_odds": 0, **self.decision}  # the first answers predate the watch prices
        return Answer(Status.OK, parsed=output_format.model_validate(d), model="pinned")


def sections(user: str) -> dict[str, str]:
    """The prompt's blocks (separated by blank lines) that start with one of SECTIONS."""
    out: dict[str, str] = {}
    for block in user.split("\n\n"):
        for name in SECTIONS:
            if block.startswith(name):
                out[name] = block
    return out


def main() -> None:
    cfg = AITraderConfig(enabled=True)
    store = ParquetHistoryStore(ROOT / "data/history")
    frames = {tf: store.load("FBS-Demo", cfg.symbol, tf, None, None) for tf in COUNTS}
    clock = ManualClock(datetime(2000, 1, 1, tzinfo=UTC))
    lane = AITraderLane(
        cfg, HistoryCandles(frames, clock), None, load_releases(ROOT / cfg.calendar_file),  # type: ignore[arg-type]
        Path("unused"), Path("unused.md"), background=False,
    )  # fmt: skip
    suspensions = json.loads((AI / "suspended.json").read_text(encoding="utf-8"))
    entries = kn.load()
    equal = calls = same_brakes = 0
    for path in sorted((AI / "raw").glob("*_3_answer.json")):
        stored = json.loads(path.read_text(encoding="utf-8"))
        if stored.get("decision") is None:
            continue
        as_of = pd.Timestamp(stored["as_of"])
        clock.set(as_of.to_pydatetime())
        fr = lane.frames()
        off = trader.suspended(suspensions, as_of)
        _, user, _ = trader.prompts(entries, fr, as_of, "", off)
        live = (path.parent / path.name.replace("_3_answer.json", "_2_user.txt")).read_text(encoding="utf-8")
        got, want = sections(user), sections(live)
        diff = [k for k in SECTIONS if got.get(k) != want.get(k)]
        rec = trader.decide(Pinned(stored["decision"]), entries, fr, as_of, "", suspensions=suspensions)
        brakes = (rec.get("final_size"), rec.get("vetoed_by")) == (stored.get("final_size"), stored.get("vetoed_by"))
        calls += 1
        equal += not diff
        same_brakes += brakes
        th = as_of.tz_convert("Asia/Bangkok")
        print(f"{th:%m-%d %H:%M} Thai  {stored['decision']['decision']:5s}  sections "
              f"{'EQUAL' if not diff else 'DIFFER: ' + ', '.join(diff)}  brakes {rec.get('final_size')} "
              f"{rec.get('vetoed_by')} ({'same' if brakes else 'stored ' + str(stored.get('final_size'))})")
        for k in diff:
            g, w = (got.get(k) or "").splitlines(), (want.get(k) or "").splitlines()
            for a, b in zip(g, w, strict=False):
                if a != b:
                    print(f"    {k} replay: {a[:150]}\n    {' ' * len(k)}   live: {b[:150]}")
                    break
            else:
                print(f"    {k}: {len(g)} lines replayed, {len(w)} live")
    print(f"{calls} calls: sections equal {equal} / {calls}; brakes equal {same_brakes} / {calls}")


if __name__ == "__main__":
    main()
