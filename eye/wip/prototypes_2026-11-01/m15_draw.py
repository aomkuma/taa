import sys; sys.path.insert(0,'.')
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt, pandas as pd
from eye import bot2e
S=r'C:\Users\korap\AppData\Local\Temp\claude\c--Users-korap-taa\600a9d86-b3ac-4124-878e-b57c675a524d\scratchpad'
a,b,name=sys.argv[1],sys.argv[2],sys.argv[3]
TH=bot2e.TH
m15=bot2e.load_frames()['M15']
full=m15[(m15.index>='2026-06-15')&(m15.index<'2026-10-31')]
pv=bot2e._zigzag(full)
flips=pd.read_pickle(S+r'\m15_flips.pkl')
start=pd.Timestamp(a,tz=TH).tz_convert('UTC'); end=pd.Timestamp(b,tz=TH).tz_convert('UTC')
bars=full[(full.index>=start)&(full.index<end)]
x=lambda t: bars.index.searchsorted(t)
plt.style.use('dark_background'); fig,ax=plt.subplots(figsize=(20,9))
# side bands
prev=[f for f in flips if f[0]<start]; side=prev[-1][1] if prev else None; t0=start
for t,s,txt in [f for f in flips if start<=f[0]<end]+[(end,None,'')]:
    if side: ax.axvspan(x(t0)-.5,x(t)-.5,color='#1565c0' if side=='BUY' else '#c62828',alpha=.18,lw=0)
    if s:
        ax.axvline(x(t)-.5,color='#90caf9' if s=='BUY' else '#ef9a9a',lw=1,ls=':')
        ax.text(x(t),bars.high.max(),f"{s}\n{t.tz_convert(TH):%d/%m %H:%M}\n{txt}",fontsize=7,va='top',color='#90caf9' if s=='BUY' else '#ef9a9a')
    side=s; t0=t
for k,(o,h,l,c) in enumerate(bars[['open','high','low','close']].to_numpy()):
    col='#2ecc71' if c>=o else '#ff4d4d'
    ax.plot([k,k],[l,h],color=col,lw=.7); ax.add_patch(plt.Rectangle((k-.32,min(o,c)),.64,max(abs(c-o),.05),color=col))
pp=[q for q in pv if start<=full.index[q.pivot_pos]<end]
ax.plot([x(full.index[q.pivot_pos]) for q in pp],[q.price for q in pp],color='#ffeb3b',lw=1.2)
for q in pp: ax.text(x(full.index[q.pivot_pos]),q.price,f"{q.price:.2f}",color='#ffeb3b',fontsize=7,ha='center',va='bottom' if q.kind.value=='HIGH' else 'top')
ticks=range(0,len(bars),16); ax.set_xticks(list(ticks)); ax.set_xticklabels([f"{bars.index[i].tz_convert(TH):%d/%m %H:%M}" for i in ticks],rotation=45,fontsize=8)
ax.yaxis.tick_right(); ax.grid(alpha=.15)
ax.set_title(f"XAUUSD M15 {a} - {b} Thai: side held until the opposite break (blue BUY after an M15 HH, red SELL after an M15 LL; the line = when it is known)")
out=f"C:/Users/korap/taa/eye/trades/m15_side_{name}.png"; fig.savefig(out,dpi=85,bbox_inches='tight'); print(out)
