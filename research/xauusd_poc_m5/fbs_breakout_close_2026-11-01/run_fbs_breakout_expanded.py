from __future__ import annotations
from collections import OrderedDict, deque
from pathlib import Path
import math,sys
import numpy as np
import pandas as pd

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from run_poc_test import HIST_DIR,TICK_DIR,ticks_between
OUT=Path(__file__).resolve().parent/'expanded_coverage'
OUT.mkdir(parents=True,exist_ok=True)
BIN=.10;LOOKBACK_H=12;HALF_H=6;EFF_MAX=.25;POC_SHIFT_MAX=.50;VA_OVERLAP_MIN=.50


def ns(series:pd.Series)->np.ndarray:
    return series.dt.as_unit('ns').astype('int64').to_numpy()

def make_hist(low:float,high:float,volume:float)->dict[int,float]:
    if volume<=0:return {}
    if high<=low:return {int(math.floor(((low+high)/2)/BIN)):float(volume)}
    first=int(math.floor(low/BIN));last=int(math.floor(high/BIN));out={};total=0.
    for k in range(first,last+1):
        overlap=max(0.,min(high,(k+1)*BIN)-max(low,k*BIN))
        if overlap>0:out[k]=overlap;total+=overlap
    if total<=0:return {int(math.floor(((low+high)/2)/BIN)):float(volume)}
    return {k:float(volume)*v/total for k,v in out.items()}

def add_hist(dst:dict[int,float],src:dict[int,float],sign:int):
    for k,v in src.items():
        z=dst.get(k,0.)+sign*v
        if z<=1e-9:dst.pop(k,None)
        else:dst[k]=z

def profile(hist:dict[int,float]):
    if not hist:return None
    lo,hi=min(hist),max(hist);counts=np.zeros(hi-lo+1,float)
    for k,v in hist.items():counts[k-lo]=v
    total=float(counts.sum())
    if total<=0:return None
    poc=int(np.argmax(counts));left=right=poc;included=float(counts[poc]);target=.70*total
    while included+1e-9<target and (left>0 or right<len(counts)-1):
        lv=float(counts[left-1]) if left>0 else -1.;rv=float(counts[right+1]) if right<len(counts)-1 else -1.
        if lv>rv:side='left'
        elif rv>lv:side='right'
        else:
            ld=abs((left-1)-poc) if left>0 else 10**9;rd=abs((right+1)-poc) if right<len(counts)-1 else 10**9
            side='left' if ld<rd else 'right'
        value=lv if side=='left' else rv
        if value<0 or included+value>target+1e-9:break
        if side=='left':left-=1;included+=value
        else:right+=1;included+=value
    return (lo+left)*BIN,(lo+poc)*BIN,(lo+right)*BIN,lo*BIN,hi*BIN,total

def main():
    m1=pd.read_parquet(HIST_DIR/'M1.parquet').sort_values('open_time').reset_index(drop=True)
    m5=pd.read_parquet(HIST_DIR/'M5.parquet').sort_values('open_time').reset_index(drop=True)
    m1_open=ns(m1.open_time);m1_close=ns(m1.close_time)
    m5_open=ns(m5.open_time);m5_close_time=ns(m5.close_time);m5_cl=m5.close.to_numpy(float)
    low=m1.low.to_numpy(float);high=m1.high.to_numpy(float);volume=m1.tick_volume.to_numpy(float)
    m1_ctx=pd.read_csv(BASE/'rolling_6h_m5'/'session_coverage.csv',parse_dates=['session_open_utc','session_close_utc'])
    sessions=m1_ctx[m1_ctx.current_m5_bars>=247].sort_values('session_open_utc').reset_index(drop=True);dev_n=int(.70*len(sessions))
    tick_cache:OrderedDict=OrderedDict();trades=[];audits=[];formations=[]
    look_ns=LOOKBACK_H*3600*1_000_000_000;half_ns=HALF_H*3600*1_000_000_000;expiry=LOOKBACK_H*12
    print(f'M1 bars={len(m1):,}, M5 bars={len(m5):,}, tick files={len(list(TICK_DIR.glob("*.parquet")))}; sessions={len(sessions)} dev={dev_n} val={len(sessions)-dev_n}',flush=True)
    for rank,s in sessions.iterrows():
        start_ns=int(pd.Timestamp(s.session_open_utc).value);end_ns=int(pd.Timestamp(s.session_close_utc).value)
        split='development' if rank<dev_n else 'validation'
        ilo=int(np.searchsorted(m1_close,start_ns-look_ns,'right'));ihi=int(np.searchsorted(m1_open,end_ns,'left'))
        if ihi<=ilo:
            audits.append({'rank':rank,'split':split,'date':s.session_date_bkk,'profile_bars':0,'cluster_formed':False,'breakout':False,'trade':False,'reason':'no_m1'});continue
        ctime=m1_close[ilo:ihi];m1l=low[ilo:ihi];m1h=high[ilo:ihi];m1v=volume[ilo:ihi]
        hists=[make_hist(float(l),float(h),float(v)) for l,h,v in zip(m1l,m1h,m1v)]
        bars_a=int(np.searchsorted(m5_open,start_ns,'left'));bars_b=int(np.searchsorted(m5_open,end_ns,'left'))
        full={};recent={};qfull=deque();qrecent=deque();ptr=0;cluster=None;cluster_formed=False;formation_i=None;qual_bars=0
        for bi in range(bars_a,bars_b):
            t=int(m5_open[bi]);cut=t-look_ns;cut_half=t-half_ns
            while qfull and ctime[qfull[0]]<=cut:
                j=qfull.popleft();add_hist(full,hists[j],-1)
            while qrecent and ctime[qrecent[0]]<=cut_half:
                j=qrecent.popleft();add_hist(recent,hists[j],-1)
            while ptr<len(ctime) and ctime[ptr]<=t:
                if ctime[ptr]>cut:
                    qfull.append(ptr);add_hist(full,hists[ptr],1)
                    if ctime[ptr]>cut_half:qrecent.append(ptr);add_hist(recent,hists[ptr],1)
                ptr+=1
            while qfull and ctime[qfull[0]]<=cut:
                j=qfull.popleft();add_hist(full,hists[j],-1)
            while qrecent and ctime[qrecent[0]]<=cut_half:
                j=qrecent.popleft();add_hist(recent,hists[j],-1)
            pf=profile(full);pnew=profile(recent)
            older={k:v-recent.get(k,0.) for k,v in full.items() if v-recent.get(k,0.)>1e-9}
            pold=profile(older)
            if pf is None or pnew is None or pold is None:continue
            val,poc,vah,range_low,range_high,total=pf;ov,op,oh,_,_,_=pold;nv,npoc,nh,_,_,_=pnew
            width_old=oh-ov;width_new=nh-nv;narrow=min(width_old,width_new)
            overlap=max(0.,min(oh,nh)-max(ov,nv));overlap_ratio=overlap/narrow if narrow>0 else 0.
            mi=int(np.searchsorted(m5_open,t,'left'));need=LOOKBACK_H*12
            if mi<need+1:continue
            prior_close=float(m5_cl[mi-1]);path=m5_cl[mi-need-1:mi]
            if len(path)<need+1:continue
            path_len=float(np.abs(np.diff(path)).sum());eff=abs(float(path[-1]-path[0]))/path_len if path_len>0 else 0.
            shift=abs(op-npoc)
            qualifies=bool(overlap_ratio>=VA_OVERLAP_MIN and shift<=POC_SHIFT_MAX and eff<=EFF_MAX and val<=prior_close<=vah)
            if qualifies:
                qual_bars+=1
                formations.append({'rank':rank,'split':split,'date':s.session_date_bkk,'time_utc':pd.Timestamp(t,unit='ns',tz='UTC'),'VAL':val,'POC':poc,'VAH':vah,'VA_overlap':overlap_ratio,'POC_shift':shift,'efficiency':eff,'profile_volume':total})
            if not cluster_formed and qualifies:
                cluster={'start_bar_i':bi,'bar_index':bi,'val':val,'poc':poc,'vah':vah,'range_low':range_low,'range_high':range_high,'formation_time':pd.Timestamp(t,unit='ns',tz='UTC')}
                cluster_formed=True;formation_i=bi
        if cluster is None:
            audits.append({'rank':rank,'split':split,'date':s.session_date_bkk,'profile_bars':qual_bars,'cluster_formed':False,'breakout':False,'trade':False,'reason':'no_cluster'});continue
        # Detect the first two-consecutive-close breakout within the frozen-cluster lifetime.
        scan_end=min(bars_b,formation_i+expiry);direction=None;break_i=None;up=down=0
        for bi in range(formation_i,scan_end):
            close=float(m5.close.iloc[bi]);
            up=up+1 if close>cluster['vah'] else 0;down=down+1 if close<cluster['val'] else 0
            if up>=2:direction='long';break_i=bi;break
            if down>=2:direction='short';break_i=bi;break
        if direction is None:
            audits.append({'rank':rank,'split':split,'date':s.session_date_bkk,'profile_bars':qual_bars,'cluster_formed':True,'formation_time_utc':cluster['formation_time'],'VAL':cluster['val'],'POC':cluster['poc'],'VAH':cluster['vah'],'breakout':False,'trade':False,'reason':'no_two_close_breakout'});continue
        signal_close_ns=int(m5_close_time[break_i]);ticks=ticks_between(pd.Timestamp(start_ns-3600*1_000_000_000,unit='ns',tz='UTC'),pd.Timestamp(end_ns,unit='ns',tz='UTC'),tick_cache)
        if ticks.empty:
            audits.append({'rank':rank,'split':split,'date':s.session_date_bkk,'profile_bars':qual_bars,'cluster_formed':True,'breakout':True,'trade':False,'reason':'no_ticks'});continue
        ticks=ticks.sort_values('time_utc',kind='mergesort').reset_index(drop=True)
        tt=ns(ticks.time_utc);bid=ticks.bid.to_numpy(float);ask=ticks.ask.to_numpy(float);spread=ask-bid
        spread_left=int(np.searchsorted(tt,signal_close_ns-3600*1_000_000_000,'left'));spread_right=int(np.searchsorted(tt,signal_close_ns,'left'))
        if spread_right<=spread_left:
            audits.append({'rank':rank,'split':split,'date':s.session_date_bkk,'profile_bars':qual_bars,'cluster_formed':True,'breakout':True,'trade':False,'reason':'no_pre_signal_spread'});continue
        median_spread=float(np.median(spread[spread_left:spread_right]));pad=max(.10,2*median_spread+.10)
        stop=cluster['vah']-pad if direction=='long' else cluster['val']+pad
        target=cluster['vah']+(cluster['vah']-cluster['val']) if direction=='long' else cluster['val']-(cluster['vah']-cluster['val'])
        entry_i=int(np.searchsorted(tt,signal_close_ns,'right'))
        if entry_i>=len(tt) or tt[entry_i]>=end_ns or tt[entry_i]-signal_close_ns>60*1_000_000_000:
            audits.append({'rank':rank,'split':split,'date':s.session_date_bkk,'profile_bars':qual_bars,'cluster_formed':True,'breakout':True,'trade':False,'reason':'no_post_close_quote_or_delay_over_60s'});continue
        entry=float(ask[entry_i] if direction=='long' else bid[entry_i])
        if (direction=='long' and not (cluster['vah']<entry<target)) or (direction=='short' and not (target<entry<cluster['val'])):
            audits.append({'rank':rank,'split':split,'date':s.session_date_bkk,'profile_bars':qual_bars,'cluster_formed':True,'breakout':True,'trade':False,'reason':'entry_back_inside_or_past_target','side':direction,'entry':entry,'VAL':cluster['val'],'VAH':cluster['vah']});continue
        risk=entry-stop
        if direction=='short':risk=stop-entry
        if risk<=0:
            audits.append({'rank':rank,'split':split,'date':s.session_date_bkk,'profile_bars':qual_bars,'cluster_formed':True,'breakout':True,'trade':False,'reason':'invalid_risk'});continue
        exit_type=None;exit_px=None;exit_i=None
        if direction=='long':
            if bid[entry_i]<=stop:exit_type='stop_at_entry';exit_px=float(bid[entry_i]);exit_i=entry_i
            else:
                fut=bid[entry_i+1:];sidx=np.flatnonzero(fut<=stop);tidx=np.flatnonzero(fut>=target)
                si=int(sidx[0])+entry_i+1 if len(sidx) else len(tt);ti=int(tidx[0])+entry_i+1 if len(tidx) else len(tt)
                if si<ti:exit_i=si;exit_type='stop';exit_px=float(bid[si])
                elif ti<len(tt):exit_i=ti;exit_type='target';exit_px=float(bid[ti])
        else:
            if ask[entry_i]>=stop:exit_type='stop_at_entry';exit_px=float(ask[entry_i]);exit_i=entry_i
            else:
                fut=ask[entry_i+1:];sidx=np.flatnonzero(fut>=stop);tidx=np.flatnonzero(fut<=target)
                si=int(sidx[0])+entry_i+1 if len(sidx) else len(tt);ti=int(tidx[0])+entry_i+1 if len(tidx) else len(tt)
                if si<ti:exit_i=si;exit_type='stop';exit_px=float(ask[si])
                elif ti<len(tt):exit_i=ti;exit_type='target';exit_px=float(ask[ti])
        if exit_type is None:
            exit_i=len(tt)-1;exit_type='session_close';exit_px=float(bid[exit_i] if direction=='long' else ask[exit_i])
        pnl=exit_px-entry if direction=='long' else entry-exit_px
        trades.append({'lookback_h':LOOKBACK_H,'rank':rank,'split':split,'date':s.session_date_bkk,'cluster_time_utc':cluster['formation_time'],'breakout_time_utc':pd.Timestamp(signal_close_ns,unit='ns',tz='UTC'),'entry_time_utc':pd.Timestamp(tt[entry_i],unit='ns',tz='UTC'),'side':direction,'entry':entry,'stop':stop,'target':target,'VAL':cluster['val'],'POC':cluster['poc'],'VAH':cluster['vah'],'VA_width':cluster['vah']-cluster['val'],'median_spread_1h':median_spread,'stop_pad':pad,'exit_time_utc':pd.Timestamp(tt[exit_i],unit='ns',tz='UTC'),'exit':exit_type,'exit_price':exit_px,'pnl':pnl,'risk':risk,'R':pnl/risk})
        audits.append({'rank':rank,'split':split,'date':s.session_date_bkk,'profile_bars':qual_bars,'cluster_formed':True,'formation_time_utc':cluster['formation_time'],'VAL':cluster['val'],'POC':cluster['poc'],'VAH':cluster['vah'],'breakout':True,'breakout_time_utc':pd.Timestamp(signal_close_ns,unit='ns',tz='UTC'),'trade':True,'reason':'filled','side':direction})
    tr=pd.DataFrame(trades);tr.to_csv(OUT/'trades.csv',index=False);pd.DataFrame(audits).to_csv(OUT/'session_audit.csv',index=False);pd.DataFrame(formations).to_csv(OUT/'qualifying_profiles.csv',index=False)
    sums=[];folds=[];dec=[]
    for split in ['development','validation','all']:
        x=tr[tr.split==split] if split!='all' else tr
        pos=x.loc[x.R>0,'R'].sum();neg=-x.loc[x.R<0,'R'].sum()
        sums.append({'strategy':'12h_confirmed_breakout_market_entry','split':split,'trades':len(x),'wins':int((x.R>0).sum()),'win_pct':100*(x.R>0).mean() if len(x) else np.nan,'net_points_per_oz':x.pnl.sum(),'net_R':x.R.sum(),'mean_R':x.R.mean(),'PF_R':pos/neg if neg else np.inf,'targets':int(x.exit.eq('target').sum()),'stops':int(x.exit.str.startswith('stop').sum())})
    fr=[]
    for f in range(3):
        lo,hi=f*dev_n//3,(f+1)*dev_n//3;x=tr[(tr["rank"]>=lo)&(tr["rank"]<hi)];pos=x.loc[x.R>0,'R'].sum();neg=-x.loc[x.R<0,'R'].sum();fr.append(float(x.R.sum()));folds.append({'fold':f+1,'trades':len(x),'net_R':x.R.sum(),'mean_R':x.R.mean(),'PF_R':pos/neg if neg else np.inf})
    dv=tr[tr.split=='development'];va=tr[tr.split=='validation'];dec.append({'development_trades':len(dv),'positive_dev_folds':sum(v>0 for v in fr),'validation_net_R':va.R.sum(),'candidate':bool(len(dv)>=20 and sum(v>0 for v in fr)>=2 and va.R.sum()>0)})
    pd.DataFrame(sums).to_csv(OUT/'summary.csv',index=False);pd.DataFrame(folds).to_csv(OUT/'development_folds.csv',index=False);pd.DataFrame(dec).to_csv(OUT/'selection.csv',index=False)
    print(pd.DataFrame(sums).to_string(index=False));print('\nFOLDS\n',pd.DataFrame(folds).to_string(index=False));print('\nSELECTION\n',pd.DataFrame(dec).to_string(index=False));print('\nAUDIT\n',pd.DataFrame(audits).groupby(['split','cluster_formed','breakout','trade','reason'],dropna=False).size().to_string())
if __name__=='__main__':main()



