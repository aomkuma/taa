from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'dukascopy_crossfeed_2026-10-31'/'data';FORM=ROOT/'dukascopy_crossfeed_2026-10-31'/'cluster_formations.csv';OUT=Path(__file__).resolve().parent

def main():
 b=pd.read_csv(DATA/'xauusd-m1-bid-2025-10-01-2026-10-29.csv');a=pd.read_csv(DATA/'xauusd-m1-ask-2025-10-01-2026-10-29.csv');b=b.rename(columns={c:f'{c}_b' for c in b if c!='timestamp'});a=a.rename(columns={c:f'{c}_a' for c in a if c!='timestamp'});d=b.merge(a,on='timestamp',validate='one_to_one').sort_values('timestamp').reset_index(drop=True);d=d[(d.low_a>=d.low_b)&(d.high_a>=d.high_b)].reset_index(drop=True);ts=d.timestamp.to_numpy(np.int64)*1_000_000
 d['m5ns']=(ts//300_000_000_000)*300_000_000_000;m5=d.groupby('m5ns',sort=True).agg(high=('high_b','max'),low=('low_b','min'),close=('close_b','last')).reset_index();mt=m5.m5ns.to_numpy(np.int64);mh=m5.high.to_numpy(float);ml=m5.low.to_numpy(float);mc=m5.close.to_numpy(float)
 cov=pd.read_csv(ROOT/'rolling_6h_m5'/'session_coverage.csv',parse_dates=['session_open_utc','session_close_utc']).query('included').sort_values('session_open_utc').reset_index(drop=True);devn=int(.7*len(cov));fm=pd.read_csv(FORM);fm['time_utc']=pd.to_datetime(fm.time_utc,utc=True);first=fm.sort_values('time_utc').groupby(['lookback_h','session_rank'],as_index=False).first();trades=[];audit=[]
 for h in (6,12):
  fs=first[first.lookback_h==h].set_index('session_rank')
  for rank,s in cov.iterrows():
   split='development' if rank<devn else 'validation';en=int(pd.Timestamp(s.session_close_utc).value);mz=np.searchsorted(mt,en)
   if rank not in fs.index:audit.append({'hours':h,'rank':rank,'split':split,'cluster':False,'breakout':False});continue
   f=fs.loc[rank];val=float(f.VAL);poc=float(f.POC);vah=float(f.VAH);width=vah-val;fi=np.searchsorted(mt,int(pd.Timestamp(f.time_utc).value));limit_i=min(mz,fi+h*12);direction=None;bi=None;up=down=0
   for i in range(fi,limit_i):
    up=up+1 if mc[i]>vah else 0;down=down+1 if mc[i]<val else 0
    if up>=2:direction='long';bi=i;break
    if down>=2:direction='short';bi=i;break
   if direction is None:audit.append({'hours':h,'rank':rank,'split':split,'cluster':True,'breakout':False});continue
   # Enter at first minute open after the second consecutive M5 close.
   entry_time=int(mt[bi]+300_000_000_000);ei=int(np.searchsorted(ts,entry_time));endq=int(np.searchsorted(ts,en))
   if ei>=endq:audit.append({'hours':h,'rank':rank,'split':split,'cluster':True,'breakout':True,'trade':False});continue
   if direction=='long':
    if d.open_a.iloc[ei]<=vah or d.open_a.iloc[ei]>=vah+width:audit.append({'hours':h,'rank':rank,'split':split,'cluster':True,'breakout':True,'trade':False,'direction':direction});continue
    side='long';entry=float(d.open_a.iloc[ei]);edge=vah;target=vah+width;stop=vah-max(.1,2*float((d.close_a.iloc[max(0,ei-60):ei]-d.close_b.iloc[max(0,ei-60):ei]).median())+.1)
   else:
    if d.open_b.iloc[ei]>=val or d.open_b.iloc[ei]<=val-width:audit.append({'hours':h,'rank':rank,'split':split,'cluster':True,'breakout':True,'trade':False,'direction':direction});continue
    side='short';entry=float(d.open_b.iloc[ei]);edge=val;target=val-width;stop=val+max(.1,2*float((d.close_a.iloc[max(0,ei-60):ei]-d.close_b.iloc[max(0,ei-60):ei]).median())+.1)
   risk=entry-stop if side=='long' else stop-entry
   if risk<=0:audit.append({'hours':h,'rank':rank,'split':split,'cluster':True,'breakout':True,'trade':False,'direction':direction});continue
   ex=xp=None
   for j in range(ei,endq):
    if side=='long':
     if d.low_b.iloc[j]<=stop:ex='stop_same_minute' if j==ei else 'stop';xp=float(d.low_b.iloc[j]);break
     if j>ei and d.high_b.iloc[j]>=target:ex='target';xp=target;break
    else:
     if d.high_a.iloc[j]>=stop:ex='stop_same_minute' if j==ei else 'stop';xp=float(d.high_a.iloc[j]);break
     if j>ei and d.low_a.iloc[j]<=target:ex='target';xp=target;break
   if ex is None:ex='session_close';xp=float(d.close_b.iloc[endq-1] if side=='long' else d.close_a.iloc[endq-1])
   pnl=xp-entry if side=='long' else entry-xp
   trades.append({'lookback_h':h,'rank':rank,'split':split,'date':s.session_date_bkk,'side':side,'cluster_time':f.time_utc,'breakout_time':pd.Timestamp(mt[bi]+300_000_000_000,unit='ns',tz='UTC'),'entry_time':pd.Timestamp(ts[ei],unit='ns',tz='UTC'),'entry':entry,'VAL':val,'POC':poc,'VAH':vah,'stop':stop,'target':target,'exit_price':xp,'exit':ex,'pnl':pnl,'risk':risk,'R':pnl/risk});audit.append({'hours':h,'rank':rank,'split':split,'cluster':True,'breakout':True,'trade':True,'direction':side})
 tr=pd.DataFrame(trades);tr.to_csv(OUT/'trades.csv',index=False);pd.DataFrame(audit).to_csv(OUT/'session_audit.csv',index=False);summ=[];fold=[];sel=[]
 for h,g in tr.groupby('lookback_h'):
  for sp in ['development','validation','all']:
   x=g[g.split==sp] if sp!='all' else g;win=x[x.R>0];loss=-x.loc[x.R<0,'R'].sum();summ.append({'hours':h,'split':sp,'trades':len(x),'wins':int((x.R>0).sum()),'win_pct':100*(x.R>0).mean() if len(x) else np.nan,'net_R':x.R.sum(),'mean_R':x.R.mean(),'PF_R':win.R.sum()/loss if loss else np.inf,'targets':int(x.exit.eq('target').sum()),'stops':int(x.exit.str.startswith('stop').sum())})
  fr=[]
  for i in range(3):
   a,b=i*devn//3,(i+1)*devn//3;x=g[(g['rank']>=a)&(g['rank']<b)];r=x.R.sum();fr.append(r);fold.append({'hours':h,'fold':i+1,'trades':len(x),'net_R':r})
  dv=g[g.split=='development'];va=g[g.split=='validation'];sel.append({'hours':h,'dev_trades':len(dv),'positive_folds':sum(r>0 for r in fr),'validation_R':va.R.sum(),'candidate':len(dv)>=20 and sum(r>0 for r in fr)>=2 and va.R.sum()>0})
 pd.DataFrame(summ).to_csv(OUT/'summary.csv',index=False);pd.DataFrame(fold).to_csv(OUT/'development_folds.csv',index=False);pd.DataFrame(sel).to_csv(OUT/'selection.csv',index=False);print(pd.DataFrame(summ).to_string(index=False));print('\nFOLDS\n',pd.DataFrame(fold).to_string(index=False));print('\nSELECT\n',pd.DataFrame(sel).to_string(index=False));print('\nAUDIT\n',pd.DataFrame(audit).groupby(['hours','split','breakout','trade']).size().to_string())
if __name__=='__main__':main()
