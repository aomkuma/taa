"""The bot's S2 planner (app/strategy/release_straddle.py) replayed on the ticks of every CPI / NFP release with
ticks, against the news agent's frozen S2 (agents/news/s2_ticks.py, D 2, S 8, exit +60 s). Same fill model as the
research: the entry at the triggering tick's ask (BUY) / bid (SELL) +- 0.07, the stop S from the fill on the bid /
ask, out at the last tick before +60 s.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/shadow/s2_replay.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path.cwd()))
from app.core.enums import Side  # noqa: E402
from app.news.releases import load_releases  # noqa: E402
from app.strategy.release_straddle import ReleaseStraddle, StraddleParams  # noqa: E402

SLIP = 0.07
TICKS = Path("data/ticks/XAUUSD")
rel = load_releases(Path("research/2026-10-18-moments/us_releases.csv"))
plan = ReleaseStraddle(StraddleParams(), rel)
rows = []
for r in plan.releases:
    f = TICKS / f"{r.at:%Y-%m-%d}.parquet"
    if not f.exists():
        continue
    d = pd.read_parquet(f)
    d["t"] = pd.to_datetime(d.time_utc, utc=True)
    t0 = pd.Timestamp(r.at)
    w = d[(d.t >= t0 - pd.Timedelta(seconds=30)) & (d.t < t0 + pd.Timedelta(seconds=120))].reset_index(drop=True)
    entry = None
    for i, q in enumerate(w.itertuples()):
        e = plan.on_quote(q.t.to_pydatetime(), q.bid, q.ask)
        if e is not None:
            entry = (i, e)
            break
    if entry is None:
        rows.append(dict(t=t0, event=r.event, side=0, usd=0.0, exit="none"))
        continue
    i, e = entry
    s = 1 if e.side is Side.BUY else -1
    fill = w.ask[i] + SLIP if s > 0 else w.bid[i] - SLIP
    after = w.iloc[i + 1 :]
    after = after[after.t < pd.Timestamp(e.close_at)]
    adv = (after.bid - fill) if s > 0 else (fill - after.ask)
    hit = after[adv <= -e.stop_distance]
    q = hit.iloc[0] if len(hit) else (after.iloc[-1] if len(after) else w.iloc[i])
    px = q.bid - SLIP if s > 0 else q.ask + SLIP
    rows.append(dict(t=t0, event=r.event, side=s, fill_s=(w.t[i] - t0).total_seconds(), usd=(px - fill) * s,
                     exit="stop" if len(hit) else "time"))
z = pd.DataFrame(rows)
ref = pd.concat([pd.read_parquet(f"research/2026-10-18-moments/agents/news/s2_ticks_{p}_h60_d2.parquet") for p in ("design", "test")])
ref = ref[ref.who == "rule"][["t", "side", "usd", "exit"]].rename(columns={"side": "ref_side", "usd": "ref_usd", "exit": "ref_exit"})
ref["t"] = pd.to_datetime(ref.t, utc=True)
m = z.merge(ref, on="t", how="outer")
pd.set_option("display.width", 200)
print(m.round(2).to_string(index=False))
both = m.dropna(subset=["ref_usd", "usd"])
print(f"\nbot planner: {int((z.side != 0).sum())} trades, {z.usd.sum():+.1f} USD | research: {len(ref)} trades, {ref.ref_usd.sum():+.1f} USD |"
      f" same side {(both.side == both.ref_side).mean():.0%}, max |diff| {(both.usd - both.ref_usd).abs().max():.2f} USD")
