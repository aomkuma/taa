"""The research's door to the AI trader (TAA-1804): the logic lives in app/ai/trader.py (one code path, PLAN §A37);
this wrapper builds the provider from .env (AI_API_KEY / AI_MODEL), loads the stored history and the owner's
suspensions, and keeps the raw prompts and answers in ai/ (raw/, decisions.jsonl). Never trades.

    .venv/Scripts/python research/2026-10-23-entry/ai_trader.py AS_OF_UTC [JOURNAL.md]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "knowledge"))
import kb  # noqa: E402
from observe import KEYS  # noqa: E402

from app.ai import trader as T  # noqa: E402
from app.ai.trader import JOURNAL_CHARS, STAND_ASIDE, StepDecision, brakes, tail  # noqa: E402,F401
from app.ai.providers import AnthropicProvider  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.core.clock import SystemClock  # noqa: E402

STORE = HERE / "ai"
OUT = STORE / "decisions.jsonl"
SUSPENDED = STORE / "suspended.json"  # rules the owner suspends for a while: {"R01": "2026-10-23T22:00:00+00:00"}


def trim_reads(text: str) -> str:
    """Only the readers' lines that carry a reading (observe.KEYS), as the hourly diary keeps them."""
    return "\n".join(ln.strip() for ln in text.splitlines() if KEYS.search(ln) and not ln.startswith("#"))


def suspensions(path: Path = SUSPENDED) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def decide(as_of: pd.Timestamp, journal: str, model: str | None = None, source: str = "manual") -> dict:
    """One AI decision at ``as_of`` through app/ai/trader.decide on the stored history."""
    env = load_settings(env_file=str(ROOT / ".env")).env
    if env.AI_API_KEY is None:
        raise SystemExit("AI_API_KEY is not set")
    provider = AnthropicProvider(env.AI_API_KEY.get_secret_value(), SystemClock(), model=env.AI_MODEL,
                                 effort=T.EFFORT, timeout_seconds=180)
    return T.decide(provider, kb.load(), kb.frames(), as_of, journal, model=model, suspensions=suspensions(),
                    store=STORE, source=source)


def main() -> None:
    as_of = pd.Timestamp(sys.argv[1], tz="UTC")
    journal = Path(sys.argv[2]).read_text(encoding="utf-8") if len(sys.argv) > 2 else ""
    print(json.dumps(decide(as_of, journal), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
