from __future__ import annotations
from collections import OrderedDict, deque
from pathlib import Path
import sys
import numpy as np
import pandas as pd
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from run_poc_test import HIST_DIR, simulate, ticks_between
OUT=Path(__file__).resolve().parent
BIN=.10; LOOKBACK=pd.Timedelta(hours=6); HALF=pd.Timedelta(hours=3)

def make_hist(low:float,high:float,volume:float)->dict[int,float]:
    if volume<=0:return {}
    if high<=low:
        return {int(np.floor(((low+high)/2)/BIN)):float(volume)}
    first=int(np.floor(low/BIN)); last=int(np.floor(high/BIN)); widths={}; total=0.0
    for k in range(first,last+1):
        w=max(0.0,min(high,(k+1)*BIN)-max(low,k*BIN))
        if w>0:widths[k]=w;total+=w
    if total<=0:return {int(np.floor(((low+high)/2)/BIN)):float(volume)}
    return {k:float(volume)*w/total for k,w in widths.items()}

def add_hist(dst,src,sign):
    for k,v in src.items():
        x=dst.get(k,0.0)+sign*v
        if x<=1e-9:dst.pop(k,None)
        else:dst[k]=x

def profile(hist):
    if not hist:return None
    lo,hi=min(hist),max(hist); c=np.zeros(hi-lo+1,float)
    for k,v in hist.items():c[k-lo]=v
    total=float(c.sum())
    if total<=0:return None
    poc=int(np.argmax(c)); left=right=poc; included=float(c[poc]); target=.70*total
    while included+1e-9<target and (left>0 or right<len(c)-1):
        lv=float(c[left-1]) if left>0 else -1.0
        rv=float(c[right+1]) if right<len(c)-1 else -1.0
        if lv>rv: side='left'
        elif rv>lv: side='right'
        else:
            ld=abs((left-1)-poc) if left>0 else 10**9
            rd=abs((right+1)-poc) if right<len(c)-1 else 10**9
            side='left' if ld<rd else 'right'
        val=lv if side=='left' else rv
        if val<0 or included+val>target+1e-9:break
        if side=='left':left-=1;included+=val
        else:right+=1;included+=val
    return (lo+left)*BIN,(lo+poc)*BIN,(lo+right)*BIN,total

def main():
    m1=pd.read_parquet(HIST_DIR/'M1.parquet').sort_values('open_time').reset_index(drop=True)
    m5=pd.read_parquet(HIST_DIR/'M5.parquet').sort_values('open_time').reset_index(drop=True)
    cov=pd.read_csv(BASE/'rolling_6h_m5'/'session_coverage.csv',parse_dates=['session_open_utc','session_close_utc'])
    sessions=cov[cov.included].sort_values('session_open_utc').reset_index(drop=True); dev_n=int(len(sessions)*.70)
    cache=OrderedDict(); trades=[]; session_audit=[]; profiles_audit=[]
    for rank,s in sessions.iterrows():
        start,end=s.session_open_utc,s.session_close_utc; split='development' if rank<dev_n else 'validation'
        bars=m5.loc[(m5.close_time>start)&(m5.close_time<=end)].copy().reset_index(drop=True)
        m1ctx=m1.loc[(m1.open_time>=start-LOOKBACK)&(m1.open_time<end)&(m1.close_time<=end)].copy().reset_index(drop=True)
        # Convert each completed M1 tick-volume bar into price-row allocations.
        hists=[make_hist(float(x.low),float(x.high),float(x.tick_volume)) for x in m1ctx.itertuples(index=False)]
        c1=m1ctx.close_time; m5ctx=m5.loc[(m5.close_time>start-LOOKBACK)&(m5.open_time<end)].copy().reset_index(drop=True); c5=m5ctx.close_time
        ticks=ticks_between(start-LOOKBACK,end,cache); tt=ticks.time_utc
        spreads=(ticks.ask.to_numpy()-ticks.bid.to_numpy()) if len(ticks) else np.array([])
        h6={};h3={};q6=deque();q3=deque();ptr=0;rows=[]
        for bar in bars.itertuples(index=False):
            t=bar.open_time;cut6=t-LOOKBACK;cut3=t-HALF
            while q6 and c1.iloc[q6[0]]<=cut6:
                j=q6.popleft();add_hist(h6,hists[j],-1)
            while q3 and c1.iloc[q3[0]]<=cut3:
                j=q3.popleft();add_hist(h3,hists[j],-1)
            while ptr<len(m1ctx) and c1.iloc[ptr]<=t:
                if c1.iloc[ptr]>cut6:
                    q6.append(ptr);add_hist(h6,hists[ptr],1)
                    if c1.iloc[ptr]>cut3:q3.append(ptr);add_hist(h3,hists[ptr],1)
                ptr+=1
            while q6 and c1.iloc[q6[0]]<=cut6:
                j=q6.popleft();add_hist(h6,hists[j],-1)
            while q3 and c1.iloc[q3[0]]<=cut3:
                j=q3.popleft();add_hist(h3,hists[j],-1)
            old={k:v-h3.get(k,0.0) for k,v in h6.items() if v-h3.get(k,0.0)>1e-9}
            p6,po,pn=profile(h6),profile(old),profile(h3)
            if p6 is None:rows.append(None);continue
            val,poc,vah,total=p6; overlap_ratio=0.0
            if po and pn:
                oval,_,ovah,_=po;nval,_,nvah,_=pn;narrow=min(ovah-oval,nvah-nval)
                overlap=max(0.0,min(ovah,nvah)-max(oval,nval));overlap_ratio=overlap/narrow if narrow>0 else 0.0
            n6=int(((m5ctx.open_time>=cut6)&(m5ctx.close_time<=t)).sum())
            no=int(((m5ctx.open_time>=cut6)&(m5ctx.close_time<=cut3)).sum())
            nr=int(((m5ctx.open_time>=cut3)&(m5ctx.close_time<=t)).sum())
            a=int(tt.searchsorted(cut6,'left'));b=int(tt.searchsorted(t,'right'))
            spread=float(np.median(spreads[a:b])) if b>a else float('nan')
            if not np.isfinite(spread):rows.append(None);continue
            qualifies=bool(n6>=48 and no>=24 and nr>=24 and overlap_ratio>=.50)
            row={'signal_bar_open_utc':t,'close_time':bar.close_time,'open':bar.open,'high':bar.high,'low':bar.low,'close':bar.close,
                 'VAL':val,'POC':poc,'VAH':vah,'touch_zone':max(.05,2*spread),'stop_pad':max(.10,2*spread+.10),
                 'profile_tick_volume':total,'m1_bars':len(q6),'m5_profile_bars':n6,'older_half_m5_bars':no,'recent_half_m5_bars':nr,
                 'half_va_overlap_ratio':overlap_ratio,'cluster_qualifies':qualifies}
            rows.append(row)
            if qualifies:profiles_audit.append({'session_rank':rank,'split':split,'session_date_bkk':s.session_date_bkk,**row})
        d=pd.DataFrame([r for r in rows if r is not None]).reset_index(drop=True)
        if d.empty:session_audit.append({'session_rank':rank,'split':split,'date':s.session_date_bkk,'clusters':0});continue
        current_ticks=ticks_between(start,end,cache);tick_times=current_ticks.time_utc;active=None;created=False;occupied=start;day_count=0;trade_taken=False
        for i,row in d.iterrows():
            if active is None and not created and row.cluster_qualifies:
                active={'start_i':i,'val':row.VAL,'poc':row.POC,'vah':row.VAH,'pad':row.stop_pad,'up_run':0,'down_run':0}
                created=True;day_count+=1
            if active is None:continue
            if i-active['start_i']>=72:active=None;continue
            active['up_run']=active['up_run']+1 if row.close>active['vah'] else 0
            active['down_run']=active['down_run']+1 if row.close<active['val'] else 0
            if active['up_run']>=2 or active['down_run']>=2:active=None;continue
            if trade_taken or row.close_time<=occupied:continue
            left=int(tick_times.searchsorted(row.signal_bar_open_utc,side='left'))
            right=int(tick_times.searchsorted(row.close_time,side='right'))
            if right<=left:continue
            window=current_ticks.iloc[left:right]
            long_hits=np.flatnonzero(window.ask.to_numpy()<=active['val'])
            short_hits=np.flatnonzero(window.bid.to_numpy()>=active['vah'])
            candidates=[]
            if len(long_hits):candidates.append((int(long_hits[0]),'long','VAL',active['val']-active['pad']))
            if len(short_hits):candidates.append((int(short_hits[0]),'short','VAH',active['vah']+active['pad']))
            if not candidates:continue
            candidates.sort(key=lambda x:x[0])
            if len(candidates)>1 and candidates[0][0]==candidates[1][0]:continue
            j,side,level,stop=candidates[0];entry_i=left+j
            # Reject ambiguous same-bar two-edge travel, even if touch order can be read from ticks.
            if (side=='long' and len(short_hits) and int(short_hits[0])<=j) or (side=='short' and len(long_hits) and int(long_hits[0])<=j):continue
            target=active['poc'];result=simulate(current_ticks,side,entry_i,stop,target,end)
            if result is None:continue
            trade_taken=True;occupied=result['exit_time']
            trades.append({'variant':'oco_limit','session_rank':rank,'split':split,'session_date_bkk':s.session_date_bkk,
                'order_active_bar_open_utc':row.signal_bar_open_utc,'mode':'limit_touch','level':level,'side':side,'cluster_val':active['val'],
                'cluster_poc':active['poc'],'cluster_vah':active['vah'],'limit_price':active['val'] if side=='long' else active['vah'],
                'target':target,'stop':stop,**result,'r_multiple':result['pnl']/result['risk'] if result['risk']>0 else np.nan})
        day_counts=[day_count]
        session_audit.append({'session_rank':rank,'split':split,'date':s.session_date_bkk,'clusters':max(day_counts,default=0),
                              'qualifying_profile_bars':int(d.cluster_qualifies.sum())})
    tr=pd.DataFrame(trades);tr.to_csv(OUT/'trades.csv',index=False)
    pd.DataFrame(profiles_audit).to_csv(OUT/'qualifying_profile_windows.csv',index=False)
    pd.DataFrame(session_audit).to_csv(OUT/'session_audit.csv',index=False)
    def metrics(x):
        pg=x.loc[x.pnl>0,'pnl'].sum();pl=-x.loc[x.pnl<0,'pnl'].sum()
        rg=x.loc[x.r_multiple>0,'r_multiple'].sum();rl=-x.loc[x.r_multiple<0,'r_multiple'].sum()
        return {'trades':len(x),'wins':int((x.pnl>0).sum()),'win_rate_pct':100*(x.pnl>0).mean() if len(x) else np.nan,
          'net_points_per_oz':x.pnl.sum(),'net_R':x.r_multiple.sum(),'mean_R':x.r_multiple.mean(),
          'profit_factor_points':pg/pl if pl else (np.inf if pg else 0),'profit_factor_R':rg/rl if rl else (np.inf if rg else 0),
          'targets':int((x.exit_type=='target').sum()),'stops':int((x.exit_type=='stop').sum())}
    sums=[];folds=[];dec=[]
    for v in ['oco_limit']:
        x=tr[tr.variant==v]
        for split in ['development','validation','all']:
            z=x[x.split==split] if split!='all' else x
            sums.append({'variant':v,'split':split,**metrics(z)})
        fr=[]
        for f in range(3):
            lo,hi=f*dev_n//3,(f+1)*dev_n//3;z=x[(x.session_rank>=lo)&(x.session_rank<hi)]
            m=metrics(z);fr.append(m['net_R']);folds.append({'variant':v,'fold':f+1,**m})
        dv=len(x[x.split=='development']);vr=float(x.loc[x.split=='validation','r_multiple'].sum())
        dec.append({'variant':v,'development_trades':dv,'positive_folds':sum(r>0 for r in fr),'validation_net_R':vr,
                    'candidate':bool(dv>=20 and sum(r>0 for r in fr)>=2 and vr>0)})
    pd.DataFrame(sums).to_csv(OUT/'summary.csv',index=False);pd.DataFrame(folds).to_csv(OUT/'development_folds.csv',index=False);pd.DataFrame(dec).to_csv(OUT/'selection.csv',index=False)
    print('sessions',len(sessions),'dev',dev_n,'val',len(sessions)-dev_n,'selected',next((r['variant'] for r in dec if r['candidate']),'NONE'))
    print(pd.DataFrame(sums).to_string(index=False));print(pd.DataFrame(folds).to_string(index=False));print('clusters',pd.DataFrame(session_audit).clusters.sum(),'qualifying windows',len(profiles_audit))
if __name__=='__main__':main()

