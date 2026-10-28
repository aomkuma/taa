"""AI chart reader pilot through the Message Batches API (half price; owner, 2026-10-18: "can it be cheaper?").
900 x 600 images (about 720 image tokens), a small model by default. Two steps:

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/ai_charts/ask_batch.py submit [--model M] [--limit N]
    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/ai_charts/ask_batch.py collect

The key comes from .env (load_settings), never printed. Results go to answers_<model>.jsonl.
"""

from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path

import anthropic
import pandas as pd

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.config import load_settings  # noqa: E402
from research_ai_prompt import SYSTEM  # noqa: E402

DIR = Path("data/research/ai_charts" + __import__("os").environ.get("AI_CHARTS_SUFFIX", ""))
STATE = DIR / "batch_state.json"
TAG = "_v2" if "--v2" in sys.argv else ""  # the structure-rich images (render_v2.py)
PRICES = {"claude-haiku-4-5": (1.0, 5.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0)}


def client() -> anthropic.Anthropic:
    key = load_settings().env.AI_API_KEY
    if key is None:
        raise SystemExit("AI_API_KEY is not set in .env")
    return anthropic.Anthropic(api_key=key.get_secret_value(), max_retries=3, timeout=120)


def submit(model: str, limit: int | None) -> None:
    man = pd.read_parquet(DIR / "manifest.parquet")
    man = man[man.kind == "base"]
    if "--ids" in sys.argv:  # a sample: one id a line
        keep = Path(sys.argv[sys.argv.index("--ids") + 1]).read_text(encoding="utf-8").split()
        man = man[man.id.isin(keep)]
    flips = "--flips" in sys.argv  # originals first; flips only when asked (the budget)
    skip = int(sys.argv[sys.argv.index("--skip") + 1]) if "--skip" in sys.argv else 0
    have = set()
    ans = DIR / f"answers_{model}{TAG}.jsonl"
    if ans.exists():
        have = {(x["id"], x["flip"]) for x in map(json.loads, ans.read_text(encoding="utf-8").splitlines()) if x.get("decision")}
    sides = (False, True) if "--both" in sys.argv else (True,) if flips else (False,)
    jobs = [(m, f) for m in man.id for f in sides if (m, f) not in have][skip:][:limit]
    reqs = []
    for mid, flip in jobs:
        img = base64.standard_b64encode((DIR / f"{mid}{'_flip' if flip else ''}{TAG or '_s'}.png").read_bytes()).decode()
        reqs.append({"custom_id": f"{mid}{'_flip' if flip else ''}", "params": {
            "model": model, "max_tokens": 400, "system": SYSTEM, **({} if "opus" in model else {"temperature": 0}),
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img}},
                {"type": "text", "text": "Decide."}]}]}})
    b = client().messages.batches.create(requests=reqs)
    STATE.write_text(json.dumps({"id": b.id, "model": model, "n": len(reqs), "tag": TAG}), encoding="utf-8")
    print(f"submitted batch {b.id}: {len(reqs)} requests on {model}")


def collect() -> None:
    st = json.loads(STATE.read_text(encoding="utf-8"))
    c = client()
    b = c.messages.batches.retrieve(st["id"])
    print(f"batch {b.id}: {b.processing_status}, counts {b.request_counts}")
    if b.processing_status != "ended":
        return
    pin, pout = PRICES.get(st["model"], (0.0, 0.0))
    out, cost = [], 0.0
    for r in c.messages.batches.results(st["id"]):
        mid, flip = r.custom_id.removesuffix("_flip"), r.custom_id.endswith("_flip")
        rec = {"id": mid, "flip": flip}
        if r.result.type == "succeeded":
            msg = r.result.message
            text = "".join(x.text for x in msg.content if x.type == "text")
            m = re.search(r"\{.*\}", text, re.S)
            ans = json.loads(m.group(0)) if m else {}
            c_ = 0.5 * (msg.usage.input_tokens * pin + msg.usage.output_tokens * pout) / 1e6  # batch: half price
            cost += c_
            rec |= {"decision": str(ans.get("decision", "")).upper() or None, "confidence": ans.get("confidence"),
                    "reason": ans.get("reason"), "in": msg.usage.input_tokens, "out": msg.usage.output_tokens, "cost": c_}
        else:
            rec |= {"decision": None, "error": r.result.type}
        out.append(rec)
    path = DIR / f"answers_{st['model']}{st.get('tag', '')}.jsonl"
    with path.open("a", encoding="utf-8") as fh:  # batches add up; a batch is collected once (state cleared)
        fh.write("\n".join(json.dumps(x) for x in out) + "\n")
    STATE.unlink()
    print(f"{len(out)} answers -> {path}; cost about {cost:.2f} USD")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "submit":
        model = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else "claude-haiku-4-5"
        limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
        submit(model, limit)
    else:
        collect()
