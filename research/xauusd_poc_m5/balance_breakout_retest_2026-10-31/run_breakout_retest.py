from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'dukascopy_crossfeed_2026-10-31'/'data';FORM=ROOT/'dukascopy_crossfeed_2026-10-31'/'cluster_formations.csv';OUT=Path(__file__).resolve().parent

def main():
 b=pd.read_csv(DATA/'xauusd-m1-bid-2025-10-01-2026-10-29.csv');a=pd.read_csv(DATA/'xauusd-m1-ask-2025-10-01-2026-10-29.csv');b=b.rename(columns={c:f'{c}_b' for c in b if c!='timestamp'});a=a.rename(columns={c:f'{c}_a' for c in a if c!='timestamp'});d=b.merge(a,on='timestamp',validate='one_to_one').sort_values('timestamp').reset_index(drop=True);d=d[(d.low_a>=d.low_b)&(d.high_a>=d.high_b)].reset_index(drop=True)
 ts=d.timestamp.to_numpy(np.int64)*1_000_000
 d['m5ns']=(ts//300_000_000_000)*300_000_000_000;m5=d.groupby('m5ns',sort=True).agg(high=('high_b','max'),low=('low_b','min'),close=('close_b','last'),n=('timestamp','size')).reset_index();mt=m5.m5ns.to_numpy(np.int64);mh=m5.high.to_numpy(float);ml=m5.low.to_numpy(float);mc=m5.close.to_numpy(float)
 cov=pd.read_csv(ROOT/'rolling_6h_m5'/'session_coverage.csv',parse_dates=['session_open_utc','session_close_utc']).query('included').sort_values('session_open_utc').reset_index(drop=True);devn=int(.70*len(cov));forms=pd.read_csv(FORM);forms['time_utc']=pd.to_datetime(forms.time_utc,utc=True);firstforms=forms.sort_values('time_utc').groupby(['lookback_h','session_rank'],as_index=False).first();rows=[];audit=[]
 for h in (6,12):
  fset=firstforms[firstforms.lookback_h==h].set_index('session_rank')
  for rank,s in cov.iterrows():
   split='development' if rank<devn else 'validation';st=int(pd.Timestamp(s.session_open_utc).value);en=int(pd.Timestamp(s.session_close_utc).value);ma=np.searchsorted(mt,st);mz=np.searchsorted(mt,en)
   if rank not in fset.index or mz<=ma:
    audit.append({'lookback_h':h,'rank':rank,'split':split,'formed':False,'breakout':False,'trade':False});continue
   f=fset.loc[rank];ft=int(pd.Timestamp(f.time_utc).value);val=float(f.VAL);poc=float(f.POC);vah=float(f.VAH);width=vah-val;fi=int(np.searchsorted(mt,ft,'left'))
   if width<=0 or fi>=mz:audit.append({'lookback_h':h,'rank':rank,'split':split,'formed':True,'breakout':False,'trade':False});continue
   # Require two consecutive M5 closes beyond the frozen value area.
   direction=None;bi=None;ru=rd=0;limit_i=min(mz,fi+h*12)
   for i in range(fi,limit_i):
    ru=ru+1 if mc[i]>vah else 0;rd=rd+1 if mc[i]<val else 0
    if ru>=2:direction='long';bi=i;break
    if rd>=2:direction='short';bi=i;break
   if direction is None:
    audit.append({'lookback_h':h,'rank':rank,'split':split,'formed':True,'breakout':False,'trade':False});continue
   order_ns=int(mt[bi]+300_000_000_000);startq=int(np.searchsorted(ts,order_ns,'left'));endq=int(np.searchsorted(ts,en,'left'));entry_i=None
   if startq<endq:
    if direction=='long':
     cand=np.flatnonzero(d.low_a.to_numpy()[startq:endq]<=vah)
    else:
     cand=np.flatnonzero(d.high_b.to_numpy()[startq:endq]>=val)
    if len(cand):entry_i=startq+int(cand[0])
   if entry_i is None:
    audit.append({'lookback_h':h,'rank':rank,'split':split,'formed':True,'breakout':True,'direction':direction,'trade':False});continue
   entry=float(min(d.open_a.iloc[entry_i],vah) if direction=='long' else max(d.open_b.iloc[entry_i],val));stop=val if direction=='long' else vah;target=vah+width if direction=='long' else val-width;risk=entry-stop if direction=='long' else stop-entry
   if risk<=0:
    audit.append({'lookback_h':h,'rank':rank,'split':split,'formed':True,'breakout':True,'direction':direction,'trade':False});continue
   ex=None;xp=None
   # M1 OHLC replay; adverse ordering is used if stop and target both fall in one minute.
   for j in range(entry_i,endq):
    if direction=='long':
     if d.low_b.iloc[j]<=stop:ex='stop_same_minute' if j==entry_i else 'stop';xp=float(d.low_b.iloc[j]);break
     if j>entry_i and d.high_b.iloc[j]>=target:ex='target';xp=target;break
    else:
     if d.high_a.iloc[j]>=stop:ex='stop_same_minute' if j==entry_i else 'stop';xp=float(d.high_a.iloc[j]);break
     if j>entry_i and d.low_a.iloc[j]<=target:ex='target';xp=target;break
   if ex is None:
    j=endq-1;ex='session_close';xp=float(d.close_b.iloc[j] if direction=='long' else d.close_a.iloc[j])
   pnl=xp-entry if direction=='long' else entry-xp
   rows.append({'lookback_h':h,'rank':rank,'split':split,'session_date':s.session_date_bkk,'cluster_time_utc':f.time_utc,'VAL':val,'POC':poc,'VAH':vah,'VA_width':width,'breakout_direction':direction,'breakout_close_time_utc':pd.Timestamp(mt[bi]+300_000_000_000,unit='ns',tz='UTC'),'entry_time_utc':pd.Timestamp(ts[entry_i],unit='ns',tz='UTC'),'entry':entry,'stop':stop,'target':target,'exit_price':xp,'exit':ex,'pnl':pnl,'risk':risk,'R':pnl/risk})
   audit.append({'lookback_h':h,'rank':rank,'split':split,'formed':True,'breakout':True,'direction':direction,'trade':True})
 tr=pd.DataFrame(rows);tr.to_csv(OUT/'trades.csv',index=False);pd.DataFrame(audit).to_csv(OUT/'session_audit.csv',index=False);sums=[];fold=[];sel=[]
 for h,g in tr.groupby('lookback_h'):
  for split in ['development','validation','all']:
   x=g[g.split==split] if split!='all' else g;wp=x[x.R>0];loss=-x.loc[x.R<0,'R'].sum();sums.append({'lookback_h':h,'split':split,'trades':len(x),'wins':int((x.R>0).sum()),'win_pct':100*(x.R>0).mean() if len(x) else np.nan,'net_R':x.R.sum(),'mean_R':x.R.mean(),'PF_R':wp.R.sum()/loss if loss else np.inf,'targets':int(x.exit.eq('target').sum()),'stops':int(x.exit.str.startswith('stop').sum())})
  fr=[]
  for f in range(3):
   lo,hi=f*devn//3,(f+1)*devn//3;x=g[(g['rank']>=lo)&(g['rank']<hi)];n=float(x.R.sum());fr.append(n);fold.append({'lookback_h':h,'fold':f+1,'trades':len(x),'net_R':n})
  dev=g[g.split=='development'];val=g[g.split=='validation'];sel.append({'lookback_h':h,'dev_trades':len(dev),'positive_folds':sum(v>0 for v in fr),'validation_R':val.R.sum(),'candidate':len(dev)>=20 and sum(v>0 for v in fr)>=2 and val.R.sum()>0})
 pd.DataFrame(sums).to_csv(OUT/'summary.csv',index=False);pd.DataFrame(fold).to_csv(OUT/'development_folds.csv',index=False);pd.DataFrame(sel).to_csv(OUT/'selection.csv',index=False)
 print(pd.DataFrame(sums).to_string(index=False));print('\nFOLDS\n',pd.DataFrame(fold).to_string(index=False));print('\nSELECTION\n',pd.DataFrame(sel).to_string(index=False));print('\nAUDIT\n',pd.DataFrame(audit).groupby(['lookback_h','split','formed','breakout','trade']).size().to_string())
if __name__=='__main__':main()
