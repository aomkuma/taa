from __future__ import annotations
from collections import deque
from pathlib import Path
import os, math
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(__file__).resolve().parent
TEMP=Path(__file__).resolve().parent/'data'
BID=TEMP/'xauusd-m1-bid-2025-10-01-2026-10-29.csv'
ASK=TEMP/'xauusd-m1-ask-2025-10-01-2026-10-29.csv'
COV=ROOT/'rolling_6h_m5'/'session_coverage.csv'
BIN=.10

def make_hist(low,high,volume):
    if volume<=0:return {}
    if high<=low:return {int(math.floor(((low+high)/2)/BIN)):float(volume)}
    a=int(math.floor(low/BIN));b=int(math.floor(high/BIN));out={};tot=0.
    for k in range(a,b+1):
        w=max(0.,min(high,(k+1)*BIN)-max(low,k*BIN))
        if w>0:out[k]=w;tot+=w
    if tot<=0:return {int(math.floor(((low+high)/2)/BIN)):float(volume)}
    return {k:float(volume)*v/tot for k,v in out.items()}

def add_hist(dst,src,sign):
    for k,v in src.items():
        z=dst.get(k,0.)+sign*v
        if z<=1e-9:dst.pop(k,None)
        else:dst[k]=z

def profile(h):
    if not h:return None
    lo,hi=min(h),max(h);vol=np.zeros(hi-lo+1,float)
    for k,v in h.items():vol[k-lo]=v
    total=float(vol.sum())
    if total<=0:return None
    poc=int(np.argmax(vol));l=r=poc;inc=float(vol[poc]);target=.70*total
    while inc+1e-9<target and (l>0 or r<len(vol)-1):
        lv=float(vol[l-1]) if l>0 else -1.;rv=float(vol[r+1]) if r<len(vol)-1 else -1.
        if lv>rv:side='l'
        elif rv>lv:side='r'
        else:side='l' if (poc-(l-1) if l>0 else 10**9)<((r+1)-poc if r<len(vol)-1 else 10**9) else 'r'
        v=lv if side=='l' else rv
        if v<0 or inc+v>target+1e-9:break
        if side=='l':l-=1;inc+=v
        else:r+=1;inc+=v
    return (lo+l)*BIN,(lo+poc)*BIN,(lo+r)*BIN,(lo)*BIN,(hi)*BIN

def trade_result(md,first,side,entry,stop,target,session_end_ns):
    risk=entry-stop if side=='long' else stop-entry
    if risk<=0:return None
    ts=md['ts']; lb=md['lb'];hb=md['hb'];la=md['la'];ha=md['ha'];ob=md['ob'];oa=md['oa'];cb=md['cb'];ca=md['ca']
    if side=='long' and lb[first]<=stop:return (float(lb[first]),'stop_same_minute',risk)
    if side=='short' and ha[first]>=stop:return (float(ha[first]),'stop_same_minute',risk)
    end=int(np.searchsorted(ts,session_end_ns,side='left'))
    for j in range(first+1,end):
        if side=='long':
            st=lb[j]<=stop;tp=hb[j]>=target
            if st:return float(lb[j]),'stop',risk
            if tp:return float(target),'target',risk
        else:
            st=ha[j]>=stop;tp=la[j]<=target
            if st:return float(ha[j]),'stop',risk
            if tp:return float(target),'target',risk
    if end<=first:return None
    j=end-1;return (float(cb[j] if side=='long' else ca[j]),'session_close',risk)

def metrics(x):
    if not len(x):return {'trades':0,'wins':0,'win_rate_pct':np.nan,'net_usd_oz':0.,'net_R':0.,'mean_R':np.nan,'PF_R':np.nan,'targets':0,'stops':0,'ambiguous':0}
    pos=x.loc[x.pnl>0,'r'];neg=-x.loc[x.pnl<0,'r']
    return {'trades':len(x),'wins':int((x.pnl>0).sum()),'win_rate_pct':100*float((x.pnl>0).mean()),'net_usd_oz':float(x.pnl.sum()),'net_R':float(x.r.sum()),'mean_R':float(x.r.mean()),'PF_R':float(pos.sum()/neg.sum()) if neg.sum()>0 else np.inf,'targets':int((x.exit.str.startswith('target')).sum()),'stops':int(x.exit.str.startswith('stop').sum()),'ambiguous':int(x.exit.eq('ambiguous_oco').sum())}

def main():
    bid=pd.read_csv(BID);ask=pd.read_csv(ASK)
    bid=bid.rename(columns={c:f'{c}_bid' for c in bid.columns if c!='timestamp'});ask=ask.rename(columns={c:f'{c}_ask' for c in ask.columns if c!='timestamp'})
    d=bid.merge(ask,on='timestamp',how='inner',validate='one_to_one').sort_values('timestamp').reset_index(drop=True)
    d=d[(d.low_ask>=d.low_bid)&(d.high_ask>=d.high_bid)&(d.volume_bid>=0)].reset_index(drop=True)
    ts=d.timestamp.to_numpy(np.int64)*1_000_000
    d['time']=pd.to_datetime(ts,unit='ns',utc=True)
    m5=d.assign(m5ns=(ts//300_000_000_000)*300_000_000_000).groupby('m5ns',sort=True).agg(open=('open_bid','first'),high=('high_bid','max'),low=('low_bid','min'),close=('close_bid','last'),n=('timestamp','size')).reset_index()
    m5ns=m5.m5ns.to_numpy(np.int64);m5close=m5.close.to_numpy(float)
    sessions=pd.read_csv(COV,parse_dates=['session_open_utc','session_close_utc']);sessions=sessions[sessions.included].sort_values('session_open_utc').reset_index(drop=True);dev_n=int(len(sessions)*.70)
    print(f'quote bars={len(d):,}; m5 bars={len(m5):,}; sessions={len(sessions)} dev={dev_n} val={len(sessions)-dev_n}',flush=True)
    all_trades=[];audit=[];formations=[]
    # Share one profile/signal pass across both stop placements.
    for hours in (3,6,12):
      look_ns=hours*3600*1_000_000_000;half_ns=look_ns//2;expiry=hours*12
      for rank,s in sessions.iterrows():
        start_ns=int(pd.Timestamp(s.session_open_utc).value);end_ns=int(pd.Timestamp(s.session_close_utc).value);split='development' if rank<dev_n else 'validation'
        lo=int(np.searchsorted(ts,start_ns-look_ns,'left'));hi=int(np.searchsorted(ts,end_ns,'left'))
        if hi<=lo:continue
        # Local arrays keep the rolling profile state small.
        q=d.iloc[lo:hi].reset_index(drop=True);qts=ts[lo:hi];nb=len(q)
        histlist=[make_hist(float(a),float(b),float(v)) for a,b,v in zip(q.low_bid,q.high_bid,q.volume_bid)]
        md={'ts':qts,'lb':q.low_bid.to_numpy(float),'hb':q.high_bid.to_numpy(float),'la':q.low_ask.to_numpy(float),'ha':q.high_ask.to_numpy(float),'ob':q.open_bid.to_numpy(float),'oa':q.open_ask.to_numpy(float),'cb':q.close_bid.to_numpy(float),'ca':q.close_ask.to_numpy(float),'spr':(q.close_ask-q.close_bid).to_numpy(float)}
        ma=int(np.searchsorted(m5ns,start_ns,'left'));mz=int(np.searchsorted(m5ns,end_ns,'left'))
        full={};half={};qfull=deque();qhalf=deque();ptr=0;states={m:None for m in ('tight','profile_extreme')};created={m:False for m in states};taken={m:False for m in states};qualbars=0;trade_counts={m:0 for m in states};ambig={m:0 for m in states}
        for bi in range(ma,mz):
            t=int(m5ns[bi]);cut=t-look_ns;cut_half=t-half_ns
            while qfull and qts[qfull[0]]<cut:
                j=qfull.popleft();add_hist(full,histlist[j],-1)
            while qhalf and qts[qhalf[0]]<cut_half:
                j=qhalf.popleft();add_hist(half,histlist[j],-1)
            while ptr<nb and qts[ptr]<t:
                qfull.append(ptr);add_hist(full,histlist[ptr],1)
                if qts[ptr]>=cut_half:qhalf.append(ptr);add_hist(half,histlist[ptr],1)
                ptr+=1
            while qfull and qts[qfull[0]]<cut:
                j=qfull.popleft();add_hist(full,histlist[j],-1)
            while qhalf and qts[qhalf[0]]<cut_half:
                j=qhalf.popleft();add_hist(half,histlist[j],-1)
            pf=profile(full);old={k:v-half.get(k,0.) for k,v in full.items() if v-half.get(k,0.)>1e-9};po=profile(old);pn=profile(half)
            if pf is None or po is None or pn is None:continue
            val,poc,vah,rlo,rhi=pf;ov,op,oh,_,_=po;nv,npoc,nh,_,_=pn
            nar=min(oh-ov,nh-nv);overlap=max(0.,min(oh,nh)-max(ov,nv));ratio=overlap/nar if nar>0 else 0.
            mi=int(np.searchsorted(m5ns,t,'left'));need=hours*12
            if mi<need:continue
            prior=float(m5close[mi-1]);path=m5close[mi-need-1:mi]
            if len(path)<need+1:continue
            den=float(np.abs(np.diff(path)).sum());eff=abs(float(path[-1]-path[0]))/den if den else 0.
            shift=abs(op-npoc);qual=bool(ratio>=.50 and eff<=.25 and shift<=.50 and val<=prior<=vah)
            if qual:qualbars+=1
            if qual:
                formations.append({'lookback_h':hours,'session_rank':rank,'split':split,'time_utc':pd.Timestamp(t,unit='ns',tz='UTC'),'VAL':val,'POC':poc,'VAH':vah,'VA_overlap':ratio,'efficiency':eff,'half_POC_shift':shift})
            if not any(created.values()) and qual:
                spreada=int(np.searchsorted(qts,t-look_ns,'left'));spreadb=int(np.searchsorted(qts,t,'left'));spr=float(np.nanmedian(md['spr'][spreada:spreadb]))
                if not np.isfinite(spr):continue
                pad=max(.10,2*spr+.10)
                for mode in states:
                    states[mode]={'start':bi,'val':val,'poc':poc,'vah':vah,'stop_long':(rlo-pad if mode=='profile_extreme' else val-pad),'stop_short':(rhi+pad if mode=='profile_extreme' else vah+pad),'above':0,'below':0}
                    created[mode]=True
            for mode in states:
                state=states[mode]
                if state is None or taken[mode]:continue
                if bi-state['start']>=expiry:states[mode]=None;continue
                if qual and state['val']<=prior<=state['vah']:
                    a=int(np.searchsorted(qts,t,'left'));z=int(np.searchsorted(qts,t+300_000_000_000,'left'))
                    long_hits=np.flatnonzero(md['la'][a:z]<=state['val']);short_hits=np.flatnonzero(md['hb'][a:z]>=state['vah'])
                    if len(long_hits) or len(short_hits):
                        first_l=a+int(long_hits[0]) if len(long_hits) else 10**18;first_s=a+int(short_hits[0]) if len(short_hits) else 10**18
                        if first_l==first_s:ambig[mode]+=1
                        else:
                            side='long' if first_l<first_s else 'short';ei=min(first_l,first_s)
                            entry=min(float(md['oa'][ei]),state['val']) if side=='long' else max(float(md['ob'][ei]),state['vah'])
                            stop=state['stop_long'] if side=='long' else state['stop_short'];target=state['poc']
                            result=trade_result(md,ei,side,entry,stop,target,end_ns)
                            if result:
                                xp,ex,risk=result;pnl=xp-entry if side=='long' else entry-xp
                                all_trades.append({'lookback_h':hours,'stop_mode':mode,'session_rank':rank,'split':split,'session_date':s.session_date_bkk,'signal_time_utc':pd.Timestamp(t,unit='ns',tz='UTC'),'entry_time_utc':pd.Timestamp(qts[ei],unit='ns',tz='UTC'),'side':side,'entry':entry,'stop':stop,'target':target,'exit_price':xp,'exit':ex,'pnl':pnl,'risk':risk,'r':pnl/risk,'VA_overlap':ratio,'efficiency':eff,'half_POC_shift':shift,'spread_at_entry':float(md['spr'][ei])})
                                taken[mode]=True;trade_counts[mode]+=1
                if not taken[mode]:
                    state['above']=state['above']+1 if m5close[bi]>state['vah'] else 0;state['below']=state['below']+1 if m5close[bi]<state['val'] else 0
                    if state['above']>=2 or state['below']>=2:states[mode]=None
        for mode in states:
            audit.append({'lookback_h':hours,'stop_mode':mode,'session_rank':rank,'split':split,'session_date':s.session_date_bkk,'qualifying_m5_bars':qualbars,'trades':trade_counts[mode],'ambiguous_oco_bars':ambig[mode]})
      print(f'finished {hours}h profiles',flush=True)
    tr=pd.DataFrame(all_trades);tr.to_csv(OUT/'trades.csv',index=False);pd.DataFrame(audit).to_csv(OUT/'session_audit.csv',index=False);pd.DataFrame(formations).to_csv(OUT/'cluster_formations.csv',index=False)
    sums=[];folds=[];sel=[]
    for (hours,mode),g in tr.groupby(['lookback_h','stop_mode']):
      for sp in ('development','validation','all'):
        z=g[g.split==sp] if sp!='all' else g;sums.append({'lookback_h':hours,'stop_mode':mode,'split':sp,**metrics(z)})
      fr=[]
      for f in range(3):
        aa,bb=f*dev_n//3,(f+1)*dev_n//3;z=g[(g.session_rank>=aa)&(g.session_rank<bb)];m=metrics(z);fr.append(m['net_R']);folds.append({'lookback_h':hours,'stop_mode':mode,'fold':f+1,**m})
      dv=len(g[g.split=='development']);vr=float(g.loc[g.split=='validation','r'].sum());pos=sum(v>0 for v in fr)
      sel.append({'lookback_h':hours,'stop_mode':mode,'dev_trades':dv,'positive_dev_folds':pos,'validation_net_R':vr,'candidate':bool(dv>=20 and pos>=2 and vr>0)})
    pd.DataFrame(sums).to_csv(OUT/'summary.csv',index=False);pd.DataFrame(folds).to_csv(OUT/'development_folds.csv',index=False);pd.DataFrame(sel).to_csv(OUT/'selection.csv',index=False)
    print('\nSUMMARY\n'+pd.DataFrame(sums).to_string(index=False));print('\nFOLDS\n'+pd.DataFrame(folds).to_string(index=False));print('\nSELECTION\n'+pd.DataFrame(sel).to_string(index=False));print('ambiguous OCO bars',int(pd.DataFrame(audit).ambiguous_oco_bars.sum()))
if __name__=='__main__':main()

