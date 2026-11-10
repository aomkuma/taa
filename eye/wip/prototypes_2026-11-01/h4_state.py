"""Prototype: H4 trend held until the opposite break - HH makes it up, LL makes it down (fixed pivots only)."""
import sys; sys.path.insert(0,'.')
import pandas as pd
from eye import bot2e
f=bot2e.load_frames()
def state(now):
    h4=bot2e.cut(f,now)['H4'].tail(1500)
    pv=bot2e._zigzag(h4)
    st, why='none',''
    lastH=lastL=None
    for q in pv:
        if q.kind.value=='HIGH':
            if lastH is not None and q.price>lastH.price: st,why='up',f"HH {lastH.price:.0f}->{q.price:.0f} ({h4.index[q.pivot_pos].tz_convert(bot2e.TH):%d/%m})"
            lastH=q
        else:
            if lastL is not None and q.price<lastL.price: st,why='down',f"LL {lastL.price:.0f}->{q.price:.0f} ({h4.index[q.pivot_pos].tz_convert(bot2e.TH):%d/%m})"
            lastL=q
    return st, why, h4.close.iloc[-1]
prev=None
for d in pd.date_range('2026-07-01','2026-10-30',freq='D'):
    now=pd.Timestamp(f"{d:%Y-%m-%d} 07:00",tz=bot2e.TH).tz_convert('UTC')
    st,why,c=state(now)
    if (st,why)!=prev: print(f"{d:%Y-%m-%d} {st:5s} {why}  close {c:.0f}")
    prev=(st,why)
