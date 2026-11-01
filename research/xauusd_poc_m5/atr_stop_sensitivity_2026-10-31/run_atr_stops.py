from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'dukascopy_crossfeed_2026-10-31'/'data';SRC=ROOT/'cluster_lifecycle_2026-10-31'/'trades.csv';OUT=Path(__file__).resolve().parent

def main():
 b=pd.read_csv(DATA/'xauusd-m1-bid-2025-10-01-2026-10-29.csv');a=pd.read_csv(DATA/'xauusd-m1-ask-2025-10-01-2026-10-29.csv')
 b=b.rename(columns={c:f'{c}_b' for c in b if c!='timestamp'});a=a.rename(columns={c:f'{c}_a' for c in a if c!='timestamp'});d=b.merge(a,on='timestamp',validate='one_to_one').sort_values('timestamp').reset_index(drop=True)
 ts=d.timestamp.to_numpy(np.int64)*1_000_000
 m5ns=(ts//300_000_000_000)*300_000_000_000;m5=pd.DataFrame({'t':m5ns,'h':d.high_b,'l':d.low_b,'c':d.close_b}).groupby('t',sort=True).agg(h=('h','max'),l=('l','min'),c=('c','last')).reset_index();prev=m5.c.shift();tr=pd.concat([m5.h-m5.l,(m5.h-prev).abs(),(m5.l-prev).abs()],axis=1).max(axis=1);m5['atr14']=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean();m5t=m5.t.to_numpy(np.int64);atr=m5.atr14.to_numpy(float)
 cov=pd.read_csv(ROOT/'rolling_6h_m5'/'session_coverage.csv',parse_dates=['session_open_utc','session_close_utc']).query('included').sort_values('session_open_utc').reset_index(drop=True);ends=cov.session_close_utc
 endns=np.array([int(pd.Timestamp(x).value) for x in ends],np.int64)
 trades=pd.read_csv(SRC);trades=trades[(trades.setup=='limit')].copy();trades['entry_ns']=pd.to_datetime(trades.entry_time,utc=True).dt.as_unit('ns').astype('int64');trades['stop_mode']='original_profile_extreme';out=[]
 # Original profile-extreme result is retained for comparison.
 for r in trades.itertuples():out.append({'lookback_h':r.lookback_h,'mode':'profile_extreme','rank':r.rank,'split':r.split,'side':r.side,'R':r.R,'pnl':r.pnl,'exit':r.exit})
 # Recompute the same fills with spread-protected stops at several ATR offsets beyond the frozen VA boundary.
 for r in trades.itertuples(index=False):
  first=int(np.searchsorted(ts,r.entry_ns,'left'));end=int(np.searchsorted(ts,endns[int(r.rank)],'left'))
  if first>=len(d) or first>=end:continue
  base_ns=(m5ns[first] if first<len(m5ns) else m5ns[-1]);mi=int(np.searchsorted(m5t,base_ns,'left'))-1;a14=atr[mi] if 0<=mi<len(atr) else np.nan
  # Spread floor is the median of the prior 6 hours, known before the entry bar opens.
  sa=int(np.searchsorted(ts,r.entry_ns-6*3600*1_000_000_000,'left'));sb=first
  med=float(np.nanmedian((d.close_a-d.close_b).to_numpy(float)[sa:sb])) if sb>sa else .5
  floor=max(.10,2*med+.10)
  boundary=float(r.VAL if r.side=='long' else r.VAH)
  for k in (0.,.10,.20,.30,.50,.75,1.0):
   off=max(floor,k*a14) if np.isfinite(a14) else floor
   stop=boundary-off if r.side=='long' else boundary+off
   risk=r.entry-stop if r.side=='long' else stop-r.entry
   if risk<=0:continue
   xp=None;exit_type=None
   for j in range(first,end):
    if r.side=='long':
     stop_hit=d.low_b.iloc[j]<=stop;target_hit=(j>first and d.high_b.iloc[j]>=r.target)
     if stop_hit:xp=float(d.low_b.iloc[j]);exit_type='stop_same_minute' if j==first else 'stop';break
     if target_hit:xp=float(r.target);exit_type='target';break
    else:
     stop_hit=d.high_a.iloc[j]>=stop;target_hit=(j>first and d.low_a.iloc[j]<=r.target)
     if stop_hit:xp=float(d.high_a.iloc[j]);exit_type='stop_same_minute' if j==first else 'stop';break
     if target_hit:xp=float(r.target);exit_type='target';break
   if xp is None:
    j=end-1;xp=float(d.close_b.iloc[j] if r.side=='long' else d.close_a.iloc[j]);exit_type='session_close'
   pnl=xp-r.entry if r.side=='long' else r.entry-xp
   out.append({'lookback_h':r.lookback_h,'mode':f'{k:.2f}ATR_floor','rank':r.rank,'split':r.split,'side':r.side,'R':pnl/risk,'pnl':pnl,'exit':exit_type,'risk':risk,'atr14':a14,'stop_offset':off})
 res=pd.DataFrame(out);res.to_csv(OUT/'trade_outcomes.csv',index=False)
 devn=int(.70*len(cov));sums=[];folds=[];sel=[]
 for (h,mode),g in res.groupby(['lookback_h','mode']):
  for split in ('development','validation'):
   x=g[g.split==split];wins=x[x.R>0];loss=-x.loc[x.R<0,'R'].sum();sums.append({'lookback_h':h,'mode':mode,'split':split,'trades':len(x),'wins':int((x.R>0).sum()),'win_pct':100*(x.R>0).mean() if len(x) else np.nan,'net_R':x.R.sum(),'mean_R':x.R.mean(),'PF_R':wins.R.sum()/loss if loss else np.inf,'targets':int(x.exit.eq('target').sum()),'stops':int(x.exit.str.startswith('stop').sum())})
  fr=[]
  for f in range(3):
   lo,hi=f*devn//3,(f+1)*devn//3;x=g[(g['rank']>=lo)&(g['rank']<hi)];n=float(x.R.sum());fr.append(n);folds.append({'lookback_h':h,'mode':mode,'fold':f+1,'trades':len(x),'net_R':n})
  dv=g[g.split=='development'];vv=g[g.split=='validation'];sel.append({'lookback_h':h,'mode':mode,'dev_trades':len(dv),'positive_folds':sum(x>0 for x in fr),'validation_R':vv.R.sum(),'candidate':len(dv)>=20 and sum(x>0 for x in fr)>=2 and vv.R.sum()>0})
 pd.DataFrame(sums).to_csv(OUT/'summary.csv',index=False);pd.DataFrame(folds).to_csv(OUT/'development_folds.csv',index=False);pd.DataFrame(sel).to_csv(OUT/'selection.csv',index=False)
 print(pd.DataFrame(sums).to_string(index=False));print('\nFOLDS\n',pd.DataFrame(folds).to_string(index=False));print('\nSELECTION\n',pd.DataFrame(sel).to_string(index=False))
if __name__=='__main__':main()

