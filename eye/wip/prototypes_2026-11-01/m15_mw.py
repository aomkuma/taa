"""Prototype 2: the M15 side with the owner's M and W. Two fixed LOWs within TOL x the swing between them (the HIGH
between, minus the lower low) are the owner's M -> BUY; two fixed HIGHs within TOL x the swing between them are a
W -> SELL. Otherwise as before: HH -> BUY, LL (beyond the tolerance) -> SELL. The side holds until the next event."""
import sys; sys.path.insert(0,'.')
import pandas as pd
from eye import bot2e
TOL=float(sys.argv[1]) if len(sys.argv)>1 else 0.15
m15=bot2e.load_frames()['M15']
m15=m15[(m15.index>='2026-06-15')&(m15.index<'2026-10-31')]
pv=bot2e._zigzag(m15)
ev=[]; lastH=lastL=None
for i,q in enumerate(pv):
    t=m15.index[q.confirm_pos]+pd.Timedelta(minutes=15)
    mid=pv[i-1] if i>0 else None
    if q.kind.value=='HIGH':
        if lastH is not None and mid is not None:
            tol=TOL*(max(lastH.price,q.price)-mid.price)
            if abs(q.price-lastH.price)<=tol: ev.append((t,'SELL',f"W {lastH.price:.2f} / {q.price:.2f}"))
            elif q.price>lastH.price: ev.append((t,'BUY',f"HH {lastH.price:.2f}->{q.price:.2f}"))
        lastH=q
    else:
        if lastL is not None and mid is not None:
            tol=TOL*(mid.price-min(lastL.price,q.price))
            if abs(q.price-lastL.price)<=tol: ev.append((t,'BUY',f"M {lastL.price:.2f} / {q.price:.2f}"))
            elif q.price<lastL.price: ev.append((t,'SELL',f"LL {lastL.price:.2f}->{q.price:.2f}"))
        lastL=q
flips=[]; side=None
for t,s,txt in ev:
    if s!=side: flips.append((t,s,txt)); side=s
flips=[x for x in flips if x[0]>=pd.Timestamp('2026-07-01',tz='UTC')]
pd.to_pickle(flips, r'C:\Users\korap\AppData\Local\Temp\claude\c--Users-korap-taa\600a9d86-b3ac-4124-878e-b57c675a524d\scratchpad\m15_flips.pkl')
ts=pd.Series([f[0] for f in flips]); dur=(ts.shift(-1)-ts).dropna()/pd.Timedelta(hours=1)
n_mw=sum(1 for f in flips if f[2][0] in 'MW')
print(f"TOL {TOL}: {len(flips)} side changes ({n_mw} by an M or W); hold median {dur.median():.1f} h (q {dur.quantile(.25):.1f} / {dur.quantile(.75):.1f})")
for t,s,txt in flips:
    if '2026-08-10'<=f"{t.tz_convert(bot2e.TH):%Y-%m-%d}"<='2026-08-14': print(f"  {t.tz_convert(bot2e.TH):%d/%m %H:%M} {s:4s} {txt}")
