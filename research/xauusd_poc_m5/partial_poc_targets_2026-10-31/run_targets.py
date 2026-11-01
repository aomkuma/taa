from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'dukascopy_crossfeed_2026-10-31'/'data';SRC=ROOT/'cluster_lifecycle_2026-10-31'/'trades.csv';OUT=Path(__file__).resolve().parent

def main():
 b=pd.read_csv(DATA/'xauusd-m1-bid-2025-10-01-2026-10-29.csv');a=pd.read_csv(DATA/'xauusd-m1-ask-2025-10-01-2026-10-29.csv');b=b.rename(columns={c:f'{c}_b' for c in b if c!='timestamp'});a=a.rename(columns={c:f'{c}_a' for c in a if c!='timestamp'});d=b.merge(a,on='timestamp',validate='one_to_one').sort_values('timestamp').reset_index(drop=True);ts=d.timestamp.to_numpy(np.int64)*1_000_000
 cov=pd.read_csv(ROOT/'rolling_6h_m5'/'session_coverage.csv',parse_dates=['session_open_utc','session_close_utc']).query('included').sort_values('session_open_utc').reset_index(drop=True);endns=np.array([int(pd.Timestamp(z).value) for z in cov.session_close_utc],np.int64);x=pd.read_csv(SRC);x=x[(x.setup=='limit')].copy();x['entry_ns']=pd.to_datetime(x.entry_time,utc=True).dt.as_unit('ns').astype('int64');rows=[]
 for r in x.itertuples(index=False):
  first=int(np.searchsorted(ts,r.entry_ns));end=int(np.searchsorted(ts,endns[int(r.rank)]));
  if first>=end or first>=len(d):continue
  for frac in (.50,.70,.78,.88,1.0):
   target=float(r.entry+frac*(r.target-r.entry));risk=r.risk;xp=None;ex=None
   for j in range(first,end):
    if r.side=='long':
     if d.low_b.iloc[j]<=r.stop:xp=float(d.low_b.iloc[j]);ex='stop_same_minute' if j==first else 'stop';break
     if j>first and d.high_b.iloc[j]>=target:xp=target;ex='target';break
    else:
     if d.high_a.iloc[j]>=r.stop:xp=float(d.high_a.iloc[j]);ex='stop_same_minute' if j==first else 'stop';break
     if j>first and d.low_a.iloc[j]<=target:xp=target;ex='target';break
   if xp is None:xp=float(d.close_b.iloc[end-1] if r.side=='long' else d.close_a.iloc[end-1]);ex='session_close'
   pnl=xp-r.entry if r.side=='long' else r.entry-xp
   rows.append({'lookback_h':r.lookback_h,'target_fraction':frac,'rank':r.rank,'split':r.split,'date':r.date,'side':r.side,'entry':r.entry,'stop':r.stop,'poc':r.target,'target':target,'exit_price':xp,'exit':ex,'pnl':pnl,'risk':risk,'R':pnl/risk})
 z=pd.DataFrame(rows);z.to_csv(OUT/'trade_outcomes.csv',index=False);devn=int(.7*len(cov));summary=[];fold=[];sel=[]
 for (h,f),g in z.groupby(['lookback_h','target_fraction']):
  for sp in ['development','validation']:
   q=g[g.split==sp];win=q[q.R>0];loss=-q.loc[q.R<0,'R'].sum();summary.append({'hours':h,'target_fraction':f,'split':sp,'trades':len(q),'wins':int((q.R>0).sum()),'win_pct':100*(q.R>0).mean(),'net_R':q.R.sum(),'mean_R':q.R.mean(),'PF_R':win.R.sum()/loss if loss else np.inf,'targets':int(q.exit.eq('target').sum()),'stops':int(q.exit.str.startswith('stop').sum())})
  fr=[]
  for i in range(3):
   lo,hi=i*devn//3,(i+1)*devn//3;q=g[(g['rank']>=lo)&(g['rank']<hi)];v=q.R.sum();fr.append(v);fold.append({'hours':h,'target_fraction':f,'fold':i+1,'trades':len(q),'net_R':v})
  dv=g[g.split=='development'];va=g[g.split=='validation'];sel.append({'hours':h,'target_fraction':f,'dev_trades':len(dv),'positive_folds':sum(v>0 for v in fr),'validation_R':va.R.sum(),'candidate':len(dv)>=20 and sum(v>0 for v in fr)>=2 and va.R.sum()>0})
 pd.DataFrame(summary).to_csv(OUT/'summary.csv',index=False);pd.DataFrame(fold).to_csv(OUT/'development_folds.csv',index=False);pd.DataFrame(sel).to_csv(OUT/'selection.csv',index=False);print(pd.DataFrame(summary).to_string(index=False));print('\nFOLDS\n',pd.DataFrame(fold).to_string(index=False));print('\nSELECTION\n',pd.DataFrame(sel).to_string(index=False))
if __name__=='__main__':main()
