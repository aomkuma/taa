"""Prototype: the M15 side held until the opposite break - an M15 HH makes it BUY, an LL makes it SELL. Fixed
pivots only (a pivot counts from its confirm bar). One pass over the whole M15 series = the same as re-reading at
every close, since a fixed pivot never moves."""
import sys; sys.path.insert(0,'.')
import pandas as pd
from eye import bot2e
m15=bot2e.load_frames()['M15']
m15=m15[(m15.index>='2026-06-15')&(m15.index<'2026-10-31')]
pv=bot2e._zigzag(m15)
ev=[]  # (time known, side, text)
lastH=lastL=None
for q in pv:
    t=m15.index[q.confirm_pos]+pd.Timedelta(minutes=15)  # known at the close of the confirm bar
    if q.kind.value=='HIGH':
        if lastH is not None and q.price>lastH.price: ev.append((t,'BUY',f"HH {lastH.price:.2f}->{q.price:.2f}",q))
        lastH=q
    else:
        if lastL is not None and q.price<lastL.price: ev.append((t,'SELL',f"LL {lastL.price:.2f}->{q.price:.2f}",q))
        lastL=q
flips=[]; side=None
for t,s,txt,q in ev:
    if s!=side: flips.append((t,s,txt)); side=s
flips=[x for x in flips if x[0]>=pd.Timestamp('2026-07-01',tz='UTC')]
pd.to_pickle(flips, r'C:\Users\korap\AppData\Local\Temp\claude\c--Users-korap-taa\600a9d86-b3ac-4124-878e-b57c675a524d\scratchpad\m15_flips.pkl')
ts=pd.Series([f[0] for f in flips])
dur=(ts.shift(-1)-ts).dropna()/pd.Timedelta(hours=1)
print(len(flips),'side changes Jul-Oct; per month:', ts.dt.tz_convert(bot2e.TH).dt.month.value_counts().sort_index().to_dict())
print('hours a side holds: median %.1f, quartiles %.1f / %.1f' % (dur.median(), dur.quantile(.25), dur.quantile(.75)))
for t,s,txt in flips:
    if '2026-08-10'<=f"{t.tz_convert(bot2e.TH):%Y-%m-%d}"<='2026-08-14': print(f"{t.tz_convert(bot2e.TH):%d/%m %H:%M} {s:4s} {txt}")
