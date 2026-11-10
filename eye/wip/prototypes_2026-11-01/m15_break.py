"""Prototype 3 (option A): an LL is counted at the first M15 CLOSE below the latest fixed LOW by more than TOL x the
swing above it (the latest fixed HIGH after that low, minus the low); an HH at the first close above the latest
fixed HIGH by more than TOL x the swing below it. M and W stay as in prototype 2 (two fixed pivots within TOL, at
the second one's confirmation). The side holds until the next event."""
import sys; sys.path.insert(0,'.')
import pandas as pd
from eye import bot2e
TOL=float(sys.argv[1]) if len(sys.argv)>1 else 0.20
m15=bot2e.load_frames()['M15']
m15=m15[(m15.index>='2026-06-15')&(m15.index<'2026-10-31')]
pv=bot2e._zigzag(m15)
close=m15.close.to_numpy(); idx=m15.index
by_confirm={}
for i,q in enumerate(pv): by_confirm.setdefault(q.confirm_pos,[]).append(i)
known=[]; ev=[]; usedL=usedH=None
for k in range(len(m15)):
    t=idx[k]+pd.Timedelta(minutes=15)
    for i in by_confirm.get(k,[]):  # pivots fixed at this bar: M / W
        q=pv[i]; same=[p for p in known if p.kind==q.kind]
        if same and known:
            prev=same[-1]; mid=known[-1]
            sw=(max(prev.price,q.price)-mid.price) if q.kind.value=='HIGH' else (mid.price-min(prev.price,q.price))
            if abs(q.price-prev.price)<=TOL*sw:
                ev.append((t,'SELL' if q.kind.value=='HIGH' else 'BUY',f"{'W' if q.kind.value=='HIGH' else 'M'} {prev.price:.2f} / {q.price:.2f}"))
        known.append(q)
    lows=[p for p in known if p.kind.value=='LOW']; highs=[p for p in known if p.kind.value=='HIGH']
    if lows and highs:
        L=lows[-1]; hs=[h for h in highs if h.pivot_pos>L.pivot_pos]; H=highs[-1]; ls=[l for l in lows if l.pivot_pos>H.pivot_pos]
        if hs and usedL is not L and close[k] < L.price-TOL*(hs[-1].price-L.price):
            ev.append((t,'SELL',f"close {close[k]:.2f} below low {L.price:.2f}")); usedL=L
        if ls and usedH is not H and close[k] > H.price+TOL*(H.price-ls[-1].price):
            ev.append((t,'BUY',f"close {close[k]:.2f} above high {H.price:.2f}")); usedH=H
flips=[]; side=None
for t,s,txt in ev:
    if s!=side: flips.append((t,s,txt)); side=s
flips=[x for x in flips if x[0]>=pd.Timestamp('2026-07-01',tz='UTC')]
pd.to_pickle(flips, sys.argv[2])
ts=pd.Series([f[0] for f in flips]); dur=(ts.shift(-1)-ts).dropna()/pd.Timedelta(hours=1)
print(f"TOL {TOL}: {len(flips)} side changes; hold median {dur.median():.1f} h (q {dur.quantile(.25):.1f} / {dur.quantile(.75):.1f})")
