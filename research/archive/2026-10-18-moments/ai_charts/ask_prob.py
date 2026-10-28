"""AI chart reader, round 2 (owner, 2026-10-18): the clear-signal moments only (F1's C4 passes: the 72-hour
extreme), and the model gives a probability for a BUY and for a SELL instead of a decision - every answer can be
ranked, none is wasted on NONE. Haiku 4.5 (knowledge to early 2025): the design set 2025-03 .. 2026-02 (`_c4`) and
the window 2026-03 .. 10-14 (`_c4w`) are both after its cutoff.

Owner: "test one request at a time first; don't waste money". Steps, each a separate command:

    one   ID [--flip]       one synchronous request, prints the raw answer (full price, ~0.002 USD)
    submit [--limit N]      a batch (half price) of the set's originals and flips not yet answered
    collect                 fetch a finished batch, append to answers_prob_<model>.jsonl

    AI_CHARTS_SUFFIX=_c4 PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/ai_charts/ask_prob.py one m0000

Every call path checks CAP_USD against all spend recorded in this set's answers before it sends anything.
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
from pathlib import Path

import anthropic
import pandas as pd

sys.path.insert(0, str(Path.cwd()))
from app.config import load_settings  # noqa: E402

MODEL = "claude-haiku-4-5"
PRICE_IN, PRICE_OUT = 1.0, 5.0  # USD per million tokens
CAP_USD = 0.25  # this round's ceiling per set (the owner's 0.5 USD stage limit covers both sets)
DIR = Path("data/research/ai_charts" + os.environ.get("AI_CHARTS_SUFFIX", "_c4"))
ANSWERS = DIR / f"answers_prob_{MODEL}.jsonl"
STATE = DIR / "batch_state_prob.json"
EST_PER_CALL = 0.0015  # full price, measured on the first request; a batch costs half

SYSTEM = (
    "You are an experienced intraday gold (XAUUSD) trader who reads charts. You will see one image with four "
    "panels of the same market at the same moment: H1 (about 5 days; orange EMA 20, blue EMA 50), M15 (about one "
    "day; orange EMA 20), M5 (6 hours) and M1 (90 minutes). The right edge of every panel is now; only closed "
    "candles are shown. Prices and times are hidden on purpose.\n"
    "A trade will be opened at the next candle with a fixed plan: the target about one average M15 candle range "
    "from the entry, the stop about two thirds of that on the other side, closed after at most one hour.\n"
    "Estimate two probabilities from the chart: p_buy, the chance that a BUY reaches its target before its stop, "
    "and p_sell, the same for a SELL. They need not add up to 100 (a trade can end at the time limit). Use the "
    "whole 0-100 scale and be specific; equal numbers mean you see no edge either way.\n"
    'Answer with JSON only: {"p_buy": 0-100, "p_sell": 0-100, "reason": "<one short sentence>"}'
)


def spent() -> float:
    if not ANSWERS.exists():
        return 0.0
    return sum(float(json.loads(x).get("cost", 0) or 0) for x in ANSWERS.read_text(encoding="utf-8").splitlines())


def client() -> anthropic.Anthropic:
    key = load_settings().env.AI_API_KEY
    if key is None:
        raise SystemExit("AI_API_KEY is not set in .env")
    return anthropic.Anthropic(api_key=key.get_secret_value(), max_retries=2, timeout=120)


def params(mid: str, flip: bool) -> dict:
    img = base64.standard_b64encode((DIR / f"{mid}{'_flip' if flip else ''}_s.png").read_bytes()).decode()
    return {"model": MODEL, "max_tokens": 300, "temperature": 0, "system": SYSTEM, "messages": [{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img}},
        {"type": "text", "text": "Estimate."}]}]}


def record(mid: str, flip: bool, msg, share: float) -> dict:
    text = "".join(x.text for x in msg.content if x.type == "text")
    m = re.search(r"\{.*\}", text, re.S)
    try:
        ans = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        ans = {}
    cost = share * (msg.usage.input_tokens * PRICE_IN + msg.usage.output_tokens * PRICE_OUT) / 1e6
    return {"id": mid, "flip": flip, "p_buy": ans.get("p_buy"), "p_sell": ans.get("p_sell"), "reason": ans.get("reason"),
            "raw": None if ans else text[:300], "in": msg.usage.input_tokens, "out": msg.usage.output_tokens, "cost": cost}


def append(rows: list[dict]) -> None:
    with ANSWERS.open("a", encoding="utf-8") as fh:
        fh.write("".join(json.dumps(r) + "\n" for r in rows))


def one(mid: str, flip: bool) -> None:
    if spent() + EST_PER_CALL > CAP_USD:
        raise SystemExit(f"cap: spent {spent():.3f} of {CAP_USD} USD")
    req = params(mid, flip)
    temp = req.pop("temperature")  # this SDK's create() has no temperature keyword; the API takes it
    msg = client().messages.create(**req, extra_body={"temperature": temp})
    rec = record(mid, flip, msg, 1.0)
    append([rec])
    print(json.dumps(rec, indent=1))


def submit(limit: int | None) -> None:
    if STATE.exists():
        raise SystemExit("a batch is pending: collect it first")
    man = pd.read_parquet(DIR / "manifest.parquet")
    have = set()
    if ANSWERS.exists():
        have = {(x["id"], x["flip"]) for x in map(json.loads, ANSWERS.read_text(encoding="utf-8").splitlines())
                if x.get("p_buy") is not None}
    jobs = [(m, f) for m in man.id for f in (False, True) if (m, f) not in have][:limit]
    est = len(jobs) * EST_PER_CALL / 2
    if spent() + est > CAP_USD:
        raise SystemExit(f"cap: {len(jobs)} calls ~{est:.3f} USD + spent {spent():.3f} > {CAP_USD}")
    b = client().messages.batches.create(requests=[
        {"custom_id": f"{m}{'_flip' if f else ''}", "params": params(m, f)} for m, f in jobs])
    STATE.write_text(json.dumps({"id": b.id, "n": len(jobs)}), encoding="utf-8")
    print(f"submitted {b.id}: {len(jobs)} requests, about {est:.3f} USD")


def collect() -> None:
    st = json.loads(STATE.read_text(encoding="utf-8"))
    c = client()
    b = c.messages.batches.retrieve(st["id"])
    print(f"batch {b.id}: {b.processing_status}, {b.request_counts}")
    if b.processing_status != "ended":
        return
    rows = []
    for r in c.messages.batches.results(st["id"]):
        mid, flip = r.custom_id.removesuffix("_flip"), r.custom_id.endswith("_flip")
        if r.result.type == "succeeded":
            rows.append(record(mid, flip, r.result.message, 0.5))
        else:
            rows.append({"id": mid, "flip": flip, "p_buy": None, "error": r.result.type, "cost": 0.0})
    append(rows)
    STATE.unlink()
    print(f"{len(rows)} answers, batch cost {sum(r['cost'] for r in rows):.3f} USD; set total {spent():.3f} USD")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "one":
        one(sys.argv[2], "--flip" in sys.argv)
    elif cmd == "submit":
        submit(int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None)
    else:
        collect()
