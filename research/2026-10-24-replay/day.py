"""The AI trader's replay journal, one Thai day at a time (TAA-1807; owner 2026-10-24: "go day by day", a weekly
summary as the subtotal; accounts 100 USD at 7.5 % and 300 USD at 3 %, at least 0.01 lot).

One day = 07:00 Thai to 07:00 Thai the next day (00:00-24:00 UTC). The bot's own backtest runs it with the AI lane
(app.cli backtest --lane ai --ticks --ai-answers ...): the live watcher, AI trader, brakes, decision engine and tick
fills; the AI's answers come from the replay store (by input hash) or, when not stored yet, from a fresh Sonnet
session through the Claude Code CLI (no tools: it sees only the prompt). The watcher's files (decisions, prompts,
session notes, watch state) and the AI's journal.md carry over from day to day in STORE.

The 300 USD account is the engine's own run (3 % a trade, the AI's 'half' halves it). The 100 USD account takes
the same trades sized at 7.5 % of its equity (min 0.01 lot, 1 lot = 100 oz), as the PLAN-1 journal did - the AI's
prompt carries neither the account nor the positions, so the decisions are the same for both.

Labels on every report: the knowledge base was partly measured on these months (owner 2026-10-24: use it all,
labelled); the model's training data runs to about June 2026; the answer arrives at the bar close here, 5-60 s
later live; an open trade is closed at the day's end (07:00 Thai).

    .venv/Scripts/python research/2026-10-24-replay/day.py 2026-07-06          # replay and report the day
    .venv/Scripts/python research/2026-10-24-replay/day.py 2026-07-06 --report # report only (already replayed)
"""

from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
# the answerer (owner 2026-10-26: "when running tests, work with Codex - the AI now on Sonnet to use
# GPT-6-Luna"): the newest Codex CLI of the VS Code ChatGPT extension; the Claude CLI if none is installed
_CODEX = sorted(Path.home().glob(".vscode/extensions/openai.chatgpt-*/bin/windows-x86_64/codex.exe"))
CLI = (
    _CODEX[-1]
    if _CODEX
    else Path(
        r"C:\Users\korap\.vscode\extensions\anthropic.claude-code-2.1.306-win32-x64\resources\native-binary\claude.exe"
    )
)
MODEL = "gpt-6-luna" if _CODEX else "claude-sonnet-5-5"
RUN = ROOT / "data/replay/ai"  # answers/, store/, days/<date>/ (the backtest's files)
LEDGER = HERE / "ledger.csv"  # one row a day: date, trades, R, the two accounts at the day's end
START = {"acct300": 300.0, "acct100": 100.0}
RISK100 = (
    0.18  # owner 2026-10-25: covers the median stop past the liquidation zone at 0.01 lot (17.7 USD in July)
)
TH = "Asia/Bangkok"


def balances(day: date) -> dict[str, float]:
    """The two accounts at the start of ``day``: the last ledger row before it."""
    out = dict(START)
    if LEDGER.exists():
        for row in csv.DictReader(LEDGER.open(encoding="utf-8")):
            if row["date"] < day.isoformat():
                out = {"acct300": float(row["acct300"]), "acct100": float(row["acct100"])}
    return out


def check_watcher_is_not_ahead(day: date) -> None:
    """Refuse a day that sits BEFORE the watcher's last call, instead of failing silently.

    The watcher's state carries from day to day, and every wake condition is ``minutes >= cooldown``
    counted from ``last_call``. Replaying an earlier date makes that difference negative, so NOTHING
    wakes the AI and the journal reads "0 trades" as if it had looked and declined. 2025-02-25 was
    replayed against a state left at 2026-07-09 and produced exactly that (2026-10-27).
    """
    state = RUN / "store/watch_state.json"
    if not state.exists():
        return
    last = json.loads(state.read_text(encoding="utf-8")).get("last_call")
    if last and pd.Timestamp(last).date() > day:
        raise SystemExit(
            f"the watcher's last call is {pd.Timestamp(last):%Y-%m-%d %H:%M}, AFTER {day}: every wake "
            "condition counts minutes from it and would go negative, so the AI would never be woken. "
            f"Replay forwards, or clear last_call in {state} first (keep a copy)."
        )


def replay(day: date, bal300: float) -> None:
    check_watcher_is_not_ahead(day)
    out = RUN / "days" / day.isoformat()
    cmd = [
        sys.executable, "-m", "app.cli", "backtest", "--lane", "ai", "--strategies", "ai_trader",
        "--server", "FBS-Demo", "--symbols", "XAUUSD", "--ticks", "data/ticks",
        "--start", day.isoformat(), "--end", (day + timedelta(days=1)).isoformat(),
        "--balance", f"{bal300:.2f}", "--out", str(out), "--preset", "aggressive", "--risk", "6",
        "--ai-answers", str(RUN / "answers"), "--ai-store", str(RUN / "store"), "--ai-cli", str(CLI),
        "--ai-model", MODEL,
    ]  # fmt: skip
    subprocess.run(cmd, cwd=ROOT, check=True)  # noqa: S603


def size100(equity: float, risk_frac: float, stop_usd: float) -> float:
    """Lots for the 100 USD account: its risk over the stop's USD a lot, floored to 0.01, never below the 0.01
    minimum (P15: the account's size never vetoes a trade); 0 only for an empty account."""
    if equity <= 0 or stop_usd <= 0:
        return 0.0
    lots = math.floor(equity * risk_frac / (stop_usd * 100) / 0.01 + 1e-9) * 0.01
    return round(max(lots, 0.01), 2)  # P15 (owner): the 0.01-lot minimum is recorded, never a veto


KEYS = ("price", "session", "h1_vol", "h1_atr", "yesterday", "phase", "m15_rhythm", "m15_leg", "h1_rhythm",
        "h4_rhythm", "d1_rhythm", "h4_big", "d1_big", "line_dist_step", "line_break", "sweep", "climax", "runaway",
        "release_min")  # fmt: skip


def wake_reasons(at: pd.Timestamp) -> str:
    """Why the watcher woke the AI at ``at``: the heading of its entry in the Thai day's session notes."""
    th = at.tz_convert(TH)
    path = RUN / "store" / f"session_{th:%Y-%m-%d}.md"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"### {th:%H:%M} Thai - the AI woken by: "):
                return line.split("woken by: ", 1)[1]
    return "?"


def readings(at: pd.Timestamp) -> dict:
    """The readings the AI was given (the stored prompt's READINGS block)."""
    path = RUN / "store" / "raw" / f"{at.tz_convert(TH):%Y-%m-%d_%H%M}_2_user.txt"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    block = text.split("READINGS (knowledge base features):\n", 1)[1].split("\n\n", 1)[0]
    return json.loads(block)


def steps(decisions: list[dict]) -> None:
    """Every wake in full: why, what the AI read, what it decided and why, what it waits for, what it watches."""
    print("\n## Step by step\n")
    for r in decisions:
        at = pd.Timestamp(r["as_of"])
        d = r.get("decision") or {}
        f = readings(at)
        seen = ", ".join(f"{k} {f[k]}" for k in KEYS if k in f)
        print(f"### {at.tz_convert(TH):%H:%M} Thai - woken by: {wake_reasons(at)}")
        print(f"- read: {seen}")
        veto = f", vetoed by {', '.join(r['vetoed_by'])}" if r.get("vetoed_by") else ""
        print(
            f"- **{d.get('decision', r['status'])}** weapon {d.get('weapon', '-')} (size {r.get('final_size')}{veto}; confidence "
            f"{d.get('confidence')}): {d.get('setup', r.get('detail', ''))}"
        )
        if d.get("entry") is not None:
            print(f"- order: entry {d.get('entry')}, stop {d.get('stop')}, target {d.get('target')}")
            sc = r.get("stop_check")
            if sc:
                where = "past the liquidation zone" if sc["beyond"] else "SHORT of the liquidation zone"
                print(f"- stop check: the AI's {sc['ai']} vs the code's {sc['code']} - {where}")
        print(
            f"- the code sees: {', '.join(r.get('weapons_in_play') or []) or 'no weapon'}; the AI: {d.get('weapon')} "
            f"({'the same picture' if r.get('same_picture') else 'a different picture'})"
        )
        print(f"- buy ({d.get('buy_odds')} %): {d.get('buy_side')}")
        print(f"- sell ({d.get('sell_odds')} %): {d.get('sell_side')}")
        print(f"- waits for: {d.get('trigger')}")
        print(
            f"- watches: above {d.get('watch_above')} / below {d.get('watch_below')}; knowledge used: "
            f"{', '.join(d.get('kb_ids') or []) or '-'}"
        )
        for reason in d.get("reasons") or []:
            print(f"  - {reason}")
        print()


def report(day: date) -> None:
    out = RUN / "days" / day.isoformat()
    start = balances(day)
    t0 = pd.Timestamp(day.isoformat(), tz="UTC")
    decisions = [
        json.loads(x)
        for x in (RUN / "store/decisions.jsonl").read_text(encoding="utf-8").splitlines()
        if t0 <= pd.Timestamp(json.loads(x)["as_of"]) < t0 + pd.Timedelta(days=1)
    ]
    by_key = {f"step-{pd.Timestamp(r['as_of']):%Y%m%d%H%M}": r for r in decisions}
    journal = {}
    if (out / "journal.jsonl").exists():
        for line in (out / "journal.jsonl").read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            journal[row.get("signal_id")] = row
    trades = (
        list(csv.DictReader((out / "trades.csv").open(encoding="utf-8")))
        if (out / "trades.csv").exists()
        else []
    )
    th = t0.tz_convert(TH)
    print(f"# {th:%a %d %b %Y} (Thai day 07:00 - 07:00)\n")
    cost = sum(r.get("cost_usd") or 0 for r in decisions)
    judged = [r for r in decisions if r.get("same_picture") is not None]
    same_n = sum(1 for r in judged if r["same_picture"])
    print(
        f"AI woken {len(decisions)} times (Sonnet through the CLI on the plan; spend counted {cost:.3f} USD); "
        f"the code and the AI saw the same weapon picture {same_n} / {len(judged)} times (the AI decides)\n"
    )
    plans_file = RUN / "store/plans.jsonl"  # the day's plans, written by the AI before it traded (P26)
    plans = [
        json.loads(x)
        for x in (plans_file.read_text(encoding="utf-8").splitlines() if plans_file.exists() else [])
        if t0 <= pd.Timestamp(json.loads(x)["as_of"]) < t0 + pd.Timedelta(days=1)
    ]
    print("## The day's plans (written by the AI at each window's start, P26)\n")
    for pl in plans:
        at = pd.Timestamp(pl["as_of"]).tz_convert(TH)
        p = pl.get("plan")
        if p is None:
            print(f"- {at:%H:%M} {pl['kind']}: no plan ({pl['status']}: {pl.get('detail')})")
            continue
        print(f"### {at:%H:%M} Thai - {pl['kind']}: the side with the edge {p['edge_side']}\n")
        print(p["summary_th"] + "\n")
        print(f"- condition: {p['condition']}")
        print(
            "- big levels: "
            + "; ".join(f"{x['price']:.2f} {x['frame']} {x['role']} ({x['what']})" for x in p["big_levels"])
        )
        print(
            "- intraday levels: "
            + "; ".join(
                f"{x['price']:.2f} {x['frame']} {x['role']} ({x['what']})" for x in p["intraday_levels"]
            )
        )
        print(f"- the trend today: {p['trend_today']}")
        for s in p["scenarios"]:
            print(
                f"- {s['name']} {s['side']} ({s['where']}): {s['trigger']}; stop {s['stop']}, take-profit {s['take_profit']}"
            )
        fails = [a["item"] for a in p["readiness"] if a["verdict"] == "fail"]
        print(f"- readiness: failed {', '.join(fails) or 'none'}; {'; '.join(pl.get('facts') or [])}\n")
    if not plans:
        print("- none\n")
    print("| Thai | decision | AI weapon | code sees | same? | buy % | sell % | size | setup / reason |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in decisions:
        d = r.get("decision") or {}
        why = (d.get("setup") or r.get("detail") or "")[:110].replace("|", "/")
        size = r.get("final_size") or "-"
        veto = f" (vetoed {', '.join(r['vetoed_by'])})" if r.get("vetoed_by") else ""
        if r.get("shadow_vetoes") and d.get("decision") in ("BUY", "SELL"):
            veto += f" (shadow {', '.join(r['shadow_vetoes'])} would stop it)"
        code = ", ".join(r.get("weapons_in_play") or []) or "-"
        same = {True: "yes", False: "NO"}.get(r.get("same_picture"), "-")
        print(
            f"| {pd.Timestamp(r['as_of']).tz_convert(TH):%H:%M} | {d.get('decision', r['status'])} | {d.get('weapon', '-')} | "
            f"{code} | {same} | {d.get('buy_odds', '-')} | {d.get('sell_odds', '-')} | {size}{veto} | {why} |"
        )
    steps(decisions)
    eq300, eq100 = start["acct300"], start["acct100"]
    rows, r_sum = [], 0.0
    for t in trades:
        side = 1 if t["side"] == "BUY" else -1
        entry, exit_, sl = float(t["entry_price"]), float(t["exit_price"]), float(t["sl_initial"])
        rec = journal.get(t["signal_id"], {})
        key = next(
            (
                w
                for w in str(rec.get("conditions", {}).get("ai_decision", "")).replace(")", "").split()
                if w.startswith("step-")
            ),
            "",
        )
        words = str(rec.get("conditions", {}).get("ai_decision", "")).replace(")", "").split()
        plan = any(w.startswith("plan-") for w in words)  # a plan order is always half (risk_scale 0.5)
        scale = 0.5 if plan or (by_key.get(key) or {}).get("final_size") == "half" else 1.0
        stop = abs(entry - sl)
        lots = size100(eq100, RISK100 * scale, stop)
        pnl100 = side * (exit_ - entry) * lots * 100
        eq100 += pnl100
        eq300 += float(t["net"])
        r = float(t["r_multiple"]) if t["r_multiple"] else 0.0
        r_sum += r
        rows.append((t, r, pnl100, lots, rec))
    print(f"\n## Trades: {len(trades)}\n")
    if rows:
        print(
            "| in (Thai) | out (Thai) | side | entry | stop | exit | why out | R | 300 acct USD | 100 acct USD (lots) |"
        )
        print("|---|---|---|---|---|---|---|---|---|---|")
        for t, r, pnl100, lots, rec in rows:
            tin = pd.Timestamp(t["entry_time"]).tz_convert(TH)
            tout = pd.Timestamp(t["exit_time"]).tz_convert(TH)
            print(
                f"| {tin:%H:%M:%S} | {tout:%H:%M:%S} | {t['side']} | {float(t['entry_price']):.2f} | "
                f"{float(t['sl_initial']):.2f} | {float(t['exit_price']):.2f} | {t['exit_reason']} | {r:+.2f} | "
                f"{float(t['net']):+.2f} | {pnl100:+.2f} ({lots:.2f}) |"
            )
        for t, _, _, _, rec in rows:
            print(
                f"\n- {pd.Timestamp(t['entry_time']).tz_convert(TH):%H:%M} {t['side']}: {rec.get('explanation', '')}"
            )
    print(
        f"\n**Day:** {len(trades)} trades, {r_sum:+.2f} R; 300 USD account {start['acct300']:.2f} -> {eq300:.2f}; "
        f"100 USD account {start['acct100']:.2f} -> {eq100:.2f}"
    )
    print(
        "\n_Labels: the knowledge base was partly measured on these months; the model's training data runs to about "
        "June 2026; answers arrive at the bar close here (5-60 s later live); a trade open at 07:00 Thai is closed._"
    )
    rows_out = []
    if LEDGER.exists():
        rows_out = [r for r in csv.DictReader(LEDGER.open(encoding="utf-8")) if r["date"] != day.isoformat()]
    rows_out.append(
        {
            "date": day.isoformat(),
            "trades": len(trades),
            "r": round(r_sum, 2),
            "acct300": round(eq300, 2),
            "acct100": round(eq100, 2),
            "wakes": len(decisions),
        }
    )
    rows_out.sort(key=lambda r: r["date"])
    with LEDGER.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["date", "trades", "r", "acct300", "acct100", "wakes"])
        w.writeheader()
        w.writerows(rows_out)


def main() -> None:
    sys.stdout.reconfigure(
        encoding="utf-8"
    )  # the AI's notes carry arrows; the Windows console codec is cp1252
    day = date.fromisoformat(sys.argv[1])
    if "--report" not in sys.argv:
        replay(day, balances(day)["acct300"])
    report(day)
    state = RUN / "store" / "watch_state.json"
    if state.exists():
        (RUN / "days" / day.isoformat() / "watch_state_end.json").write_text(
            state.read_text(encoding="utf-8"), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
