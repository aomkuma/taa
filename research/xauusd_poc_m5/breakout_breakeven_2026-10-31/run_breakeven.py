from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'dukascopy_crossfeed_2026-10-31'/'data';SRC=ROOT/'balance_breakout_close_2026-10-31'/'trades.csv';OUT=Path(__file__).resolve().parent

def main():
 b=pd.read_csv(DATA/'xauusd-m1-bid-2025-10-01-2026-10-29.csv');a=pd.read_csv(DATA/'xauusd-m1-ask-2025-10-01-2026-10-29.csv');b=b.rename(columns={c:f'{c}_b' for c in b if c!='timestamp'});a=a.rename(columns={c:f'{c}_a' for c in a if c!='timestamp'});d=b.merge(a,on='timestamp',validate='one_to_one').sort_values('timestamp').reset_index(drop=True);ts=d.timestamp.to_numpy(np.int64)*1_000_000
 cov=pd.read_csv(ROOT/'rolling_6h_m5'/'session_coverage.csv',parse_dates=['session_open_utc','session_close_utc']).query('included').sort_values('session_open_utc').reset_index(drop=True);endns=np.array([int(pd.Timestamp(z).value) for z in cov.session_close_utc],np.int64);x=pd.read_csv(SRC);x['entry_ns']=pd.to_datetime(x.entry_time,utc=True).dt.as_unit('ns').astype('int64');rows=[]
 for r in x.itertuples(index=False):
  first=int(np.searchsorted(ts,r.entry_ns));end=int(np.searchsorted(ts,endns[int(r.rank)]));
  if first>=end:continue
  for trigger in (None,.5,1.0):
   risk=float(r.risk);be=False;xp=None;ex=None
   for j in range(first,end):
    if r.side=='long':
     st=d.low_b.iloc[j]<= (r.entry if be else r.stop);tp=(j>first and d.high_b.iloc[j]>=r.target)
     if st:xp=float(min(d.low_b.iloc[j],r.entry) if be else d.low_b.iloc[j]);ex='break_even' if be else ('stop_same_minute' if j==first else 'stop');break
     if tp:xp=float(r.target);ex='target';break
     if trigger is not None and j>first and not be and d.high_b.iloc[j]>=r.entry+trigger*risk:be=True
    else:
     st=d.high_a.iloc[j]>= (r.entry if be else r.stop);tp=(j>first and d.low_a.iloc[j]<=r.target)
     if st:xp=float(max(d.high_a.iloc[j],r.entry) if be else d.high_a.iloc[j]);ex='break_even' if be else ('stop_same_minute' if j==first else 'stop');break
     if tp:xp=float(r.target);ex='target';break
     if trigger is not None and j>first and not be and d.low_a.iloc[j]<=r.entry-trigger*risk:be=True
   if xp is None:xp=float(d.close_b.iloc[end-1] if r.side=='long' else d.close_a.iloc[end-1]);ex='session_close'
   pnl=xp-r.entry if r.side=='long' else r.entry-xp;rows.append({'lookback_h':r.lookback_h,'trigger_R':'none' if trigger is None else trigger,'rank':r.rank,'split':r.split,'side':r.side,'pnl':pnl,'risk':risk,'R':pnl/risk,'exit':ex,'breakeven_activated':be})
 y=pd.DataFrame(rows);y.to_csv(OUT/'trade_outcomes.csv',index=False);devn=int(.7*len(cov));summ=[];fold=[];sel=[]
 for (h,thr),g in y.groupby(['lookback_h','trigger_R']):
  for sp in ['development','validation']:
   q=g[g.split==sp];win=q[q.R>0];loss=-q.loc[q.R<0,'R'].sum();summ.append({'hours':h,'trigger_R':thr,'split':sp,'trades':len(q),'wins':int((q.R>0).sum()),'win_pct':100*(q.R>0).mean(),'net_R':q.R.sum(),'mean_R':q.R.mean(),'PF_R':win.R.sum()/loss if loss else np.inf,'targets':int(q.exit.eq('target').sum()),'stops':int(q.exit.str.startswith('stop').sum()),'breakeven_exits':int(q.exit.eq('break_even').sum())})
  fr=[]
  for i in range(3):
   lo,hi=i*devn//3,(i+1)*devn//3;q=g[(g['rank']>=lo)&(g['rank']<hi)];v=q.R.sum();fr.append(v);fold.append({'hours':h,'trigger_R':thr,'fold':i+1,'trades':len(q),'net_R':v})
  dv=g[g.split=='development'];va=g[g.split=='validation'];sel.append({'hours':h,'trigger_R':thr,'dev_trades':len(dv),'positive_folds':sum(v>0 for v in fr),'validation_R':va.R.sum(),'candidate':len(dv)>=20 and sum(v>0 for v in fr)>=2 and va.R.sum()>0})
 pd.DataFrame(summ).to_csv(OUT/'summary.csv',index=False);pd.DataFrame(fold).to_csv(OUT/'development_folds.csv',index=False);pd.DataFrame(sel).to_csv(OUT/'selection.csv',index=False);print(pd.DataFrame(summ).to_string(index=False));print('\nFOLDS\n',pd.DataFrame(fold).to_string(index=False));print('\nSELECTION\n',pd.DataFrame(sel).to_string(index=False))
if __name__=='__main__':main()
