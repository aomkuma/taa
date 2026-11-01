from pathlib import Path
import pandas as pd
OUT=Path(__file__).resolve().parent
tr=pd.read_csv(OUT/'trades.csv')
session_count=158;dev_n=int(session_count*.70)
def metrics(x):
    pg=x.loc[x.pnl>0,'pnl'].sum();pl=-x.loc[x.pnl<0,'pnl'].sum();rg=x.loc[x.r_multiple>0,'r_multiple'].sum();rl=-x.loc[x.r_multiple<0,'r_multiple'].sum()
    return {'trades':len(x),'wins':int((x.pnl>0).sum()),'win_rate_pct':100*(x.pnl>0).mean() if len(x) else float('nan'),
      'net_points_per_oz':x.pnl.sum(),'net_R':x.r_multiple.sum(),'mean_R':x.r_multiple.mean(),
      'profit_factor_points':pg/pl if pl else (float('inf') if pg else 0),'profit_factor_R':rg/rl if rl else (float('inf') if rg else 0),
      'targets':int((x.exit_type=='target').sum()),'stops':int((x.exit_type=='stop').sum())}
sums=[];folds=[];decisions=[]
for variant in ['rotation_only','rotation_plus_breakout']:
    part=tr[tr.variant==variant]
    for split in ['development','validation','all']:
        subset=part[part.split==split] if split!='all' else part
        sums.append({'variant':variant,'split':split,**metrics(subset)})
    fold_r=[]
    for fold in range(3):
        lo,hi=fold*dev_n//3,(fold+1)*dev_n//3
        result=metrics(part[(part.session_rank>=lo)&(part.session_rank<hi)])
        fold_r.append(result['net_R']);folds.append({'variant':variant,'fold':fold+1,**result})
    dev_trades=len(part[part.split=='development']);validation_r=float(part.loc[part.split=='validation','r_multiple'].sum())
    decisions.append({'variant':variant,'development_trades':dev_trades,'positive_folds':sum(x>0 for x in fold_r),
        'validation_net_R':validation_r,'candidate':bool(dev_trades>=20 and sum(x>0 for x in fold_r)>=2 and validation_r>0)})
pd.DataFrame(sums).to_csv(OUT/'summary.csv',index=False);pd.DataFrame(folds).to_csv(OUT/'development_folds.csv',index=False)
pd.DataFrame(decisions).to_csv(OUT/'selection.csv',index=False)
(OUT/'selected_variant.txt').write_text(next((x['variant'] for x in decisions if x['candidate']),'NONE'),encoding='utf-8')
print(pd.DataFrame(sums).to_string(index=False));print(pd.DataFrame(folds).to_string(index=False));print(pd.DataFrame(decisions).to_string(index=False))
