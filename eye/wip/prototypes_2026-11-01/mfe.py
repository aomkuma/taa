"""For each resolved fill of a research ledger: the most favourable move (in R) before its exit, and what a
closer target at k R would have done (first of stop / k-R target from the fill bar on; a bar touching both = stop,
as score.py). Research only."""
import sys, csv; sys.path.insert(0,'.')
import pandas as pd
from eye import bot2e
from eye.score import TH
led=sys.argv[1]
m5=bot2e.load_frames()['M5']
rows=[x for x in csv.DictReader(open(led,encoding='utf-8')) if x['fill'] and x['why'] in ('stop','target')]
year=2026
def ts(t): return pd.Timestamp(f"{year}-{t[3:5]}-{t[:2]} {t[6:]}",tz=TH).tz_convert('UTC')
out=[]
for x in rows:
    buy=x['side']=='BUY'; e=float(x['entry']); s=float(x['stop']); risk=abs(e-s)
    f=ts(x['fill']); bars=m5[m5.index>=f]
    mfe=0.0; res={}
    for k in (0.5,1.0,1.5,2.0): res[k]=None
    for i,(_,b) in enumerate(bars.iterrows()):
        hit_stop=(b.low<=s) if buy else (b.high>=s)
        fav=((b.high-e) if buy else (e-b.low))/risk
        for k in res:
            if res[k] is None:
                if hit_stop: res[k]=-1-0.3/risk
                elif i>0 and fav>=k: res[k]=k-0.3/risk
        if hit_stop: break
        if i>0: mfe=max(mfe,fav)
        if i>3000: break
    out.append((x,mfe,res))
win=[o for o in out if o[0]['why']=='target']; lose=[o for o in out if o[0]['why']=='stop']
print(f"{led}: {len(out)} resolved, {len(win)} won, {len(lose)} lost")
for k in (0.5,1.0,1.5):
    print(f"  losers that reached +{k} R before the stop: {sum(1 for o in lose if o[1]>=k)} of {len(lose)}")
print("  a fixed target instead:")
for k in (0.5,1.0,1.5,2.0):
    v=[o[2][k] for o in out if o[2][k] is not None]
    print(f"    {k} R: {sum(1 for r in v if r>0)} won of {len(v)} ({sum(1 for r in v if r>0)/len(v):.0%}), {sum(v):+.1f} R, {sum(v)/len(v):+.3f} R a trade")
print(f"  as run: {sum(float(o[0]['r_net']) for o in out):+.1f} R")
