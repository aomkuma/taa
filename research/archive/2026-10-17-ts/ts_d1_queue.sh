#!/bin/bash
# TS-d1 month by month over both years (2024-10 .. 2026-09), XAUUSD M15, TS alone. At most 2 of these at once and
# fewer than 4 backtests in total (the other session's OOS queue counts these too).
cd /c/Users/korap/taa
OUT=data/backtests/ts/d1
CFG=${CFG:-config_ts_d1_m15}
MONTHS=${MONTHS:-"2026-03 2026-08 2024-10 2024-11 2024-12 2025-01 2025-02 2025-03 2025-04 2025-05 2025-06 2025-07 2025-08 2025-09 2025-10 2025-11 2025-12 2026-01 2026-02 2026-04 2026-05 2026-06 2026-07 2026-09"}
live() {
  powershell -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*.venv*app.cli backtest*' }).Count" | tr -d '\r'
}
mine() {
  powershell -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*.venv*app.cli backtest*' -and \$_.CommandLine -like '*backtests/ts/d1*' }).Count" | tr -d '\r'
}
for m in $MONTHS; do
  log=$OUT/$m.log
  grep -q expectancy "$log" 2>/dev/null && continue
  y=${m%-*}; mo=$((10#${m#*-} + 1)); [ $mo -eq 13 ] && { mo=1; y=$((y + 1)); }; end=$(printf "%04d-%02d-01" $y $mo)
  while true; do
    a=$(live); sleep 2; b=$(live); c=$(mine)
    [ "${a:-9}" -lt 4 ] && [ "${b:-9}" -lt 4 ] && [ "${c:-9}" -lt 2 ] && break
    sleep 20
  done
  echo "$(date +%H:%M) start $m"
  CONFIG_FILE=data/research/$CFG.yaml ENABLE_HIGH_RISK_PROFILE=false MAX_ACCOUNT_DRAWDOWN_PERCENT=50 ALLOWED_SYMBOLS=XAUUSD \
  PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python -m app.cli backtest --server FBS-Demo --symbols XAUUSD \
    --start $m-01 --end $end --strategies setup_triple_screen --out $OUT/$m --progress > "$log" 2>&1 &
  sleep 15
done
wait
echo "$(date +%H:%M) d1 queue done"
