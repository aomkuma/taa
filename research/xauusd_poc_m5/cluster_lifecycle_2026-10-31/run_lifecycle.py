from __future__ import annotations
from collections import deque
from pathlib import Path
import os,math
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent;TMP=ROOT/'dukascopy_crossfeed_2026-10-31'/'data';BIN=.10

def hist_bar(lo,hi,v):
 if v<=0:return {}
 a=int(math.floor(lo/BIN));b=int(math.floor(hi/BIN));z={};tot=0.
 if hi<=lo:return {a:float(v)}
 for k in range(a,b+1):
  w=max(0.,min(hi,(k+1)*BIN)-max(lo,k*BIN))
  if w>0:z[k]=w;tot+=w
 return {k:float(v)*x/tot for k,x in z.items()} if tot else {a:float(v)}
def update(dst,src,s):
 for k,v in src.items():
  x=dst.get(k,0.)+s*v
  if x<=1e-9:dst.pop(k,None)
  else:dst[k]=x
def prof(h):
 if not h:return None
 lo,hi=min(h),max(h);a=np.zeros(hi-lo+1)
 for k,v in h.items():a[k-lo]=v
 tot=a.sum();p=int(np.argmax(a));l=r=p;inc=a[p];goal=.7*tot
 while inc+1e-9<goal and (l>0 or r<len(a)-1):
  lv=a[l-1] if l>0 else -1;rv=a[r+1] if r<len(a)-1 else -1
  side='l' if lv>rv or (lv==rv and p-l+1<=r-p+1) else 'r';v=lv if side=='l' else rv
  if v<0 or inc+v>goal+1e-9:break
  if side=='l':l-=1;inc+=v
  else:r+=1;inc+=v
 return (lo+l)*BIN,(lo+p)*BIN,(lo+r)*BIN,lo*BIN,hi*BIN
def sim(q,first,side,entry,stop,target,end):
 risk=entry-stop if side=='long' else stop-entry
 if risk<=0:return None
 if side=='long' and q.lb[first]<=stop:return float(q.lb[first]),'stop_same_minute',risk
 if side=='short' and q.ha[first]>=stop:return float(q.ha[first]),'stop_same_minute',risk
 for j in range(first+1,end):
  if side=='long':
   if q.lb[j]<=stop:return float(q.lb[j]),'stop',risk
   if q.hb[j]>=target:return float(target),'target',risk
  else:
   if q.ha[j]>=stop:return float(q.ha[j]),'stop',risk
   if q.la[j]<=target:return float(target),'target',risk
 j=end-1
 if j<first:return None
 return (float(q.cb[j]) if side=='long' else float(q.ca[j])),'session_close',risk
def main():
 b=pd.read_csv(TMP/'xauusd-m1-bid-2025-10-01-2026-10-29.csv');a=pd.read_csv(TMP/'xauusd-m1-ask-2025-10-01-2026-10-29.csv')
 b=b.rename(columns={c:f'{c}_b' for c in b if c!='timestamp'});a=a.rename(columns={c:f'{c}_a' for c in a if c!='timestamp'});d=b.merge(a,on='timestamp',validate='one_to_one').sort_values('timestamp').reset_index(drop=True)
 d=d[(d.low_a>=d.low_b)&(d.high_a>=d.high_b)].reset_index(drop=True);ts=d.timestamp.to_numpy(np.int64)*1_000_000
 d['m5ns']=(ts//300_000_000_000)*300_000_000_000;m5=d.groupby('m5ns',sort=True).agg(high=('high_b','max'),low=('low_b','min'),close=('close_b','last'),n=('timestamp','size')).reset_index();m5t=m5.m5ns.to_numpy(np.int64);mh=m5.high.to_numpy(float);ml=m5.low.to_numpy(float);mc=m5.close.to_numpy(float)
 cov=pd.read_csv(ROOT/'rolling_6h_m5'/'session_coverage.csv',parse_dates=['session_open_utc','session_close_utc']);cov=cov[cov.included].sort_values('session_open_utc').reset_index(drop=True);devn=int(.7*len(cov));results=[];audit=[]
 for hours in (6,12):
  L=hours*3600*10**9;half=L//2;expiry=hours*12
  for rank,s in cov.iterrows():
   st=int(pd.Timestamp(s.session_open_utc).value);en=int(pd.Timestamp(s.session_close_utc).value);split='development' if rank<devn else 'validation';left=np.searchsorted(ts,st-L);right=np.searchsorted(ts,en);q=d.iloc[left:right].reset_index(drop=True);qt=ts[left:right]
   if len(q)==0:continue
   q['profile_hist']=[hist_bar(float(x),float(y),float(v)) for x,y,v in zip(q.low_b,q.high_b,q.volume_b)]
   # Use local arrays for quick quote-side fill replay.
   class Q:pass
   z=Q();z.ts=qt;z.lb=q.low_b.to_numpy(float);z.hb=q.high_b.to_numpy(float);z.la=q.low_a.to_numpy(float);z.ha=q.high_a.to_numpy(float);z.ob=q.open_b.to_numpy(float);z.oa=q.open_a.to_numpy(float);z.cb=q.close_b.to_numpy(float);z.ca=q.close_a.to_numpy(float);z.sp=q.close_a.to_numpy(float)-q.close_b.to_numpy(float)
   ma=np.searchsorted(m5t,st);mz=np.searchsorted(m5t,en);full={};halfvol={};qf=deque();qh=deque();ptr=0;states={k:None for k in ['limit','reclaim']};made=False;done={'limit':False,'reclaim':False};cnt={'limit':0,'reclaim':0};ambiguities=0
   for ix in range(ma,mz):
    t=int(m5t[ix]);cut=t-L;ch=t-half
    while qf and qt[qf[0]]<cut:j=qf.popleft();update(full,q.profile_hist.iloc[j],-1)
    while qh and qt[qh[0]]<ch:j=qh.popleft();update(halfvol,q.profile_hist.iloc[j],-1)
    while ptr<len(q) and qt[ptr]<t:
     qf.append(ptr);update(full,q.profile_hist.iloc[ptr],1)
     if qt[ptr]>=ch:qh.append(ptr);update(halfvol,q.profile_hist.iloc[ptr],1)
     ptr+=1
    while qf and qt[qf[0]]<cut:j=qf.popleft();update(full,q.profile_hist.iloc[j],-1)
    while qh and qt[qh[0]]<ch:j=qh.popleft();update(halfvol,q.profile_hist.iloc[j],-1)
    pf=prof(full);po=prof({k:v-halfvol.get(k,0.) for k,v in full.items() if v-halfvol.get(k,0.)>1e-9});pn=prof(halfvol)
    if pf is None or po is None or pn is None:continue
    val,poc,vah,rlo,rhi=pf;ov,op,oh,_,_=po;nv,npoc,nh,_,_=pn;den=min(oh-ov,nh-nv);over=max(0.,min(oh,nh)-max(ov,nv));ovlp=over/den if den>0 else 0.
    mi=np.searchsorted(m5t,t);n=hours*12
    if mi<n:continue
    prior=mc[mi-1];path=mc[mi-n-1:mi];denom=np.abs(np.diff(path)).sum();eff=abs(path[-1]-path[0])/denom if denom else 0.;shift=abs(op-npoc)
    cluster=(ovlp>=.5 and eff<=.25 and shift<=.5 and val<=prior<=vah)
    if not made and cluster:
     a0=np.searchsorted(qt,t-L);a1=np.searchsorted(qt,t);pad=max(.1,2*float(np.nanmedian(z.sp[a0:a1]))+.1)
     states['limit']={'start':ix,'val':val,'poc':poc,'vah':vah,'sl':rlo-pad,'ss':rhi+pad,'pad':pad,'above':0,'below':0}
     states['reclaim']=dict(states['limit']);made=True
    for setup in states:
     c=states[setup]
     if c is None or done[setup]:continue
     if ix-c['start']>=expiry:states[setup]=None;continue
     # Passive order remains active while frozen cluster is valid; no need to re-qualify every bar.
     if setup=='limit' and c['val']<=prior<=c['vah']:
      aa=np.searchsorted(qt,t);zz=np.searchsorted(qt,t+300_000_000_000);inds=np.arange(aa,zz);lh=inds[z.la[aa:zz]<=c['val']];sh=inds[z.hb[aa:zz]>=c['vah']]
      il=lh[0] if len(lh) else 10**18;is_=sh[0] if len(sh) else 10**18
      if il<10**18 or is_<10**18:
       if il==is_:ambiguities+=1
       else:
        side='long' if il<is_ else 'short';ei=int(min(il,is_));entry=min(z.oa[ei],c['val']) if side=='long' else max(z.ob[ei],c['vah']);stop=c['sl'] if side=='long' else c['ss'];r=sim(z,ei,side,entry,stop,c['poc'],np.searchsorted(qt,en))
        if r:
         xp,ex,risk=r;pnl=xp-entry if side=='long' else entry-xp;results.append({'lookback_h':hours,'setup':setup,'rank':rank,'split':split,'date':s.session_date_bkk,'side':side,'entry_time':pd.Timestamp(qt[ei],unit='ns',tz='UTC'),'entry':entry,'stop':stop,'target':c['poc'],'exit_price':xp,'exit':ex,'pnl':pnl,'risk':risk,'R':pnl/risk,'overlap':ovlp,'eff':eff,'shift':shift,'VAL':c['val'],'VAH':c['vah']});done[setup]=True;cnt[setup]+=1
     elif setup=='reclaim':
      # Signal M5 bar swept VA edge and closed back inside; enter next minute open.
      sig_range=max(float(mh[ix]-ml[ix]),1e-9);sig_close=float(mc[ix])
      long_sig=(ml[ix]<=c['val'] and c['val']<sig_close<c['poc']);short_sig=(mh[ix]>=c['vah'] and c['poc']<sig_close<c['vah'])
      if long_sig or short_sig:
       ei=np.searchsorted(qt,t+300_000_000_000)
       if ei<len(qt) and qt[ei]<en:
        side='long' if long_sig and not short_sig else ('short' if short_sig and not long_sig else '')
        if side:
         entry=float(z.oa[ei] if side=='long' else z.ob[ei]);stop=float(ml[ix]-c['pad'] if side=='long' else mh[ix]+c['pad']);r=sim(z,ei,side,entry,stop,c['poc'],np.searchsorted(qt,en))
         if r:
          xp,ex,risk=r;pnl=xp-entry if side=='long' else entry-xp;results.append({'lookback_h':hours,'setup':setup,'rank':rank,'split':split,'date':s.session_date_bkk,'side':side,'entry_time':pd.Timestamp(qt[ei],unit='ns',tz='UTC'),'entry':entry,'stop':stop,'target':c['poc'],'exit_price':xp,'exit':ex,'pnl':pnl,'risk':risk,'R':pnl/risk,'overlap':ovlp,'eff':eff,'shift':shift,'signal_time':pd.Timestamp(t+300_000_000_000,unit='ns',tz='UTC'),'VAL':c['val'],'VAH':c['vah'],'signal_low':float(ml[ix]),'signal_high':float(mh[ix]),'signal_close':sig_close,'rejection_strength':((sig_close-c['val'])/sig_range if side=='long' else (c['vah']-sig_close)/sig_range)});done[setup]=True;cnt[setup]+=1
     if not done[setup]:
      c['above']=c['above']+1 if mc[ix]>c['vah'] else 0;c['below']=c['below']+1 if mc[ix]<c['val'] else 0
      if c['above']>=2 or c['below']>=2:states[setup]=None
   for setup in states:audit.append({'hours':hours,'setup':setup,'rank':rank,'split':split,'date':s.session_date_bkk,'trades':cnt[setup],'ambiguous_limit_minutes':ambiguities})
  print('finished',hours,'hours',flush=True)
 tr=pd.DataFrame(results);tr.to_csv(OUT/'trades.csv',index=False);pd.DataFrame(audit).to_csv(OUT/'session_audit.csv',index=False)
 sums=[];fold=[];dec=[]
 for (h,setup),g in tr.groupby(['lookback_h','setup']):
  for split in ('development','validation','all'):
   x=g[g.split==split] if split!='all' else g;wins=x[x.R>0];loss=-x.loc[x.R<0,'R'].sum();sums.append({'hours':h,'setup':setup,'split':split,'trades':len(x),'wins':len(wins),'win_pct':100*(len(wins)/len(x)) if len(x) else np.nan,'net_R':x.R.sum(),'mean_R':x.R.mean(),'PF_R':wins.R.sum()/loss if loss else np.inf,'targets':int(x.exit.eq('target').sum()),'stops':int(x.exit.str.startswith('stop').sum())})
  fr=[]
  for f in range(3):
   aa,bb=f*devn//3,(f+1)*devn//3;x=g[(g['rank']>=aa)&(g['rank']<bb)];r=float(x.R.sum());fr.append(r);fold.append({'hours':h,'setup':setup,'fold':f+1,'trades':len(x),'net_R':r})
  dv=len(g[g.split=='development']);vr=float(g.loc[g.split=='validation','R'].sum());dec.append({'hours':h,'setup':setup,'dev_trades':dv,'positive_folds':sum(v>0 for v in fr),'validation_R':vr,'candidate':dv>=20 and sum(v>0 for v in fr)>=2 and vr>0})
 pd.DataFrame(sums).to_csv(OUT/'summary.csv',index=False);pd.DataFrame(fold).to_csv(OUT/'development_folds.csv',index=False);pd.DataFrame(dec).to_csv(OUT/'selection.csv',index=False)
 print('\n',pd.DataFrame(sums).to_string(index=False));print('\n',pd.DataFrame(fold).to_string(index=False));print('\n',pd.DataFrame(dec).to_string(index=False));print('ambiguous limit touches',ambiguities)
if __name__=='__main__':main()


