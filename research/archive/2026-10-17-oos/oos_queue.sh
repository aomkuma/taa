#!/bin/bash
# The one launcher for the out-of-sample year: V1, F1, S1 per month, 2024-10 .. 2025-09, at most 3 at once.
# The code runs from a worktree frozen at the batch's commit (another session may edit the main tree meanwhile);
# data, configs and outputs stay in the main tree. Finished months and months already running are skipped.
MAIN=/c/Users/korap/taa
CODE=${OOS_CODE:-$MAIN/.claude/worktrees/oos-runner}
OUT=$MAIN/data/backtests/oos
SYM8=EURUSD,GBPUSD,USDJPY,USDCHF,AUDUSD,USDCAD,NZDUSD,XAUUSD
MONTHS="2024-10 2024-11 2024-12 2025-01 2025-02 2025-03 2025-04 2025-05 2025-06 2025-07 2025-08 2025-09"
cd "$CODE" || exit 1
procs() {  # the --out folders of the running backtests (each run is a venv launcher + a python child)
  powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*.venv*app.cli backtest*' } | ForEach-Object { (\$_.CommandLine -split '--out ')[1].Split(' ')[0] }" | tr -d '\r'
}
run() {  # setup month
  local s=$1 m=$2 y mo end cfg syms strat
  y=${m%-*}; mo=$((10#${m#*-} + 1)); [ $mo -eq 13 ] && { mo=1; y=$((y + 1)); }; end=$(printf "%04d-%02d-01" $y $mo)
  case $s in
    v1) cfg=config_v1_nocap; syms=$SYM8; strat=setup_harmonic_prz ;;
    f1) cfg=config_f1_nocap; syms=$SYM8; strat=setup_breakout ;;
    s1) cfg=config_scalp_s1; syms=XAUUSD; strat=setup_breakout ;;
  esac
  CONFIG_FILE=$MAIN/data/research/$cfg.yaml ENABLE_HIGH_RISK_PROFILE=false MAX_ACCOUNT_DRAWDOWN_PERCENT=50 \
  ALLOWED_SYMBOLS=$syms PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 $MAIN/.venv/Scripts/python -m app.cli backtest \
    --server FBS-Demo --data $MAIN/data/history --symbols $syms --start $m-01 --end $end --strategies $strat \
    --out $OUT/${s}_$m --progress > "$OUT/${s}_$m.log" 2>&1
}
for m in $MONTHS; do
  for s in v1 f1 s1; do
    grep -q expectancy "$OUT/${s}_$m.log" 2>/dev/null && continue
    procs | grep -q "${s}_$m\$" && continue
    while true; do  # start only when both checks see fewer than 3 runs
      a=$(procs | grep -c .); sleep 2; b=$(procs | grep -c .)
      [ "$a" -lt 3 ] && [ "$b" -lt 3 ] && break
      sleep 20
    done
    echo "$(date +%H:%M) start ${s}_$m"
    run $s $m &
    sleep 15
  done
done
wait
echo "$(date +%H:%M) queue done"
