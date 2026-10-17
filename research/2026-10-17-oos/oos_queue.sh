#!/bin/bash
# The one launcher for the out-of-sample year: V1, F1, S1 per month, 2024-10 .. 2025-09, at most 3 at once.
cd /c/Users/korap/taa
OUT=data/backtests/oos
SYM8=EURUSD,GBPUSD,USDJPY,USDCHF,AUDUSD,USDCAD,NZDUSD,XAUUSD
MONTHS="2024-10 2024-11 2024-12 2025-01 2025-02 2025-03 2025-04 2025-05 2025-06 2025-07 2025-08 2025-09"
live() {  # running backtest runs (each run is a launcher + a python child: count the venv launchers)
  powershell -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*.venv*app.cli backtest*' }).Count" | tr -d '\r'
}
run() {  # setup month
  local s=$1 m=$2 y mo end cfg syms
  local log=$OUT/${s}_$m.log
  grep -q expectancy "$log" 2>/dev/null && return
  y=${m%-*}; mo=$((10#${m#*-} + 1)); [ $mo -eq 13 ] && { mo=1; y=$((y + 1)); }; end=$(printf "%04d-%02d-01" $y $mo)
  case $s in
    v1) cfg=config_v1_nocap; syms=$SYM8; strat=setup_harmonic_prz ;;
    f1) cfg=config_f1_nocap; syms=$SYM8; strat=setup_breakout ;;
    s1) cfg=config_scalp_s1; syms=XAUUSD; strat=setup_breakout ;;
  esac
  CONFIG_FILE=data/research/$cfg.yaml ENABLE_HIGH_RISK_PROFILE=false MAX_ACCOUNT_DRAWDOWN_PERCENT=50 ALLOWED_SYMBOLS=$syms \
  PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python -m app.cli backtest --server FBS-Demo --symbols $syms \
    --start $m-01 --end $end --strategies $strat --out $OUT/${s}_$m --progress > "$log" 2>&1
}
for m in $MONTHS; do
  for s in v1 f1 s1; do
    grep -q expectancy "$OUT/${s}_$m.log" 2>/dev/null && continue
    while true; do  # start only when both checks see fewer than 3 runs
      a=$(live); sleep 2; b=$(live)
      [ "${a:-9}" -lt 3 ] && [ "${b:-9}" -lt 3 ] && break
      sleep 20
    done
    echo "$(date +%H:%M) start ${s}_$m"
    run $s $m &
    sleep 15
  done
done
wait
echo "$(date +%H:%M) queue done"
