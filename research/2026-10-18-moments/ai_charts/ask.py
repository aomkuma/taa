"""AI chart reader pilot: ask Claude about every rendered chart and its upside-down twin (docs/AI_CHART_READER.md;
owner, 2026-10-18: "do it"). App venv (anthropic SDK; the key from .env via load_settings, never printed). Answers
are cached (answers.jsonl): a rerun asks only what is missing. Stops when the spend reaches BUDGET_USD.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/ai_charts/ask.py [--limit N]
"""

from __future__ import annotations

import base64
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anthropic
import pandas as pd

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.config import load_settings  # noqa: E402

MODEL = "claude-sonnet-5-5"
PRICE_IN, PRICE_OUT = 2.0, 10.0  # USD per million tokens (app/ai/providers.py PRICES)
BUDGET_USD = 12.0
DIR = Path("data/research/ai_charts")
ANSWERS = DIR / "answers.jsonl"
from research_ai_prompt import SYSTEM  # noqa: E402

lock = threading.Lock()
spent = 0.0


def done_keys() -> set[tuple[str, bool]]:
    if not ANSWERS.exists():
        return set()
    out = set()
    for line in ANSWERS.read_text(encoding="utf-8").splitlines():
        a = json.loads(line)
        if a.get("decision") is not None:
            out.add((a["id"], a["flip"]))
    return out


def ask(client: anthropic.Anthropic, mid: str, flip: bool) -> None:
    global spent
    with lock:
        if spent >= BUDGET_USD:
            return
    img = base64.standard_b64encode((DIR / f"{mid}{'_flip' if flip else ''}.png").read_bytes()).decode()
    rec: dict[str, object] = {"id": mid, "flip": flip}
    try:
        msg = client.messages.create(
            model=MODEL,
            max_tokens=200,
            temperature=0,
            system=SYSTEM,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img}},
                {"type": "text", "text": "Decide."},
            ]}],
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        m = re.search(r"\{.*\}", text, re.S)
        ans = json.loads(m.group(0)) if m else {}
        cost = (msg.usage.input_tokens * PRICE_IN + msg.usage.output_tokens * PRICE_OUT) / 1e6
        rec |= {"decision": str(ans.get("decision", "")).upper() or None, "confidence": ans.get("confidence"),
                "reason": ans.get("reason"), "in": msg.usage.input_tokens, "out": msg.usage.output_tokens, "cost": cost}
    except Exception as exc:  # research boundary: record and go on
        rec |= {"decision": None, "error": f"{type(exc).__name__}: {exc}"[:300], "cost": 0.0}
    with lock:
        spent += float(rec.get("cost", 0.0) or 0.0)
        with ANSWERS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")


def main() -> None:
    global spent
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    key = load_settings().env.AI_API_KEY
    if key is None:
        raise SystemExit("AI_API_KEY is not set in .env")
    client = anthropic.Anthropic(api_key=key.get_secret_value(), max_retries=3, timeout=60)
    if ANSWERS.exists():
        spent = sum(float(json.loads(x).get("cost", 0) or 0) for x in ANSWERS.read_text(encoding="utf-8").splitlines())
    man = pd.read_parquet(DIR / "manifest.parquet")
    have = done_keys()
    jobs = [(m, f) for m in man.id for f in (False, True) if (m, f) not in have]
    if limit:
        jobs = jobs[:limit]
    print(f"{len(jobs)} calls to make, spent so far {spent:.2f} USD", flush=True)
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(lambda j: ask(client, *j), jobs))
    print(f"spent {spent:.2f} USD", flush=True)


if __name__ == "__main__":
    main()
