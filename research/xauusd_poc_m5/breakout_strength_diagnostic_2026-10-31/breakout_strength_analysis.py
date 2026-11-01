from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'dukascopy_crossfeed_2026-10-31'/'data';TRADES=ROOT/'balance_breakout_close_2026-10-31'/'trades.csv';OUT=Path(__file__).resolve().parent

def main():
 x=pd.read_csv(TRADES);x=x[x.lookback_h==12].copy()
 b=pd.read_csv(DATA/'xauusd-m1-bid-2025-10-01-2026-10-29.csv');ts=b.timestamp.to_numpy(np.int64)*1_000_000;b['m5']=(ts//300_000_000_000)*300_000_000_000
 m=b.groupby('m5',sort=True).agg(high=('high','max'),low=('low','min'),close=('close','last')).reset_index();prev=m.close.shift();tr=pd.concat([m.high-m.low,(m.high-prev).abs(),(m.low-prev).abs()],axis=1).max(axis=1);m['atr14']=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean();mt=m.m5.to_numpy(np.int64)
 t=pd.to_datetime(x.breakout_time,utc=True).dt.as_unit('ns').astype('int64').to_numpy();dist=[];atr_norm=[];width_norm=[];breakclose=[]
 for r,close_ns in zip(x.itertuples(),t):
  op=close_ns-300_000_000_000;i=int(np.searchsorted(mt,op));cl=float(m.close.iloc[i]);a=float(m.atr14.iloc[i]);edge=float(r.VAH if r.side=='long' else r.VAL);d=max(0.,cl-edge) if r.side=='long' else max(0.,edge-cl);w=float(r.VAH-r.VAL)
  dist.append(d);atr_norm.append(d/a if a>0 else np.nan);width_norm.append(d/w if w>0 else np.nan);breakclose.append(cl)
 x['breakout_close']=breakclose;x['distance_beyond_edge']=dist;x['distance_atr14']=atr_norm;x['distance_value_width']=width_norm;x.to_csv(OUT/'trade_strength.csv',index=False)
 rows=[]
 for col,levels in [('distance_atr14',[0,.1,.25,.5,1.]),('distance_value_width',[0,.05,.1,.2,.3])]:
  for gte in levels:
   q=x[x[col]>=gte]
   folds=[]
   for f in range(3):
    lo,hi=f*110//3,(f+1)*110//3;y=q[(q['rank']>=lo)&(q['rank']<hi)];folds.append(float(y.R.sum()))
   d=q[q.split=='development'];v=q[q.split=='validation'];rows.append({'feature':col,'minimum':gte,'dev_trades':len(d),'dev_R':d.R.sum(),'dev_folds_R':','.join(f'{z:.2f}' for z in folds),'validation_trades':len(v),'validation_R':v.R.sum(),'validation_wins':int((v.R>0).sum())})
 pd.DataFrame(rows).to_csv(OUT/'threshold_summary.csv',index=False);print(pd.DataFrame(rows).round(2).to_string(index=False))
if __name__=='__main__':main()
