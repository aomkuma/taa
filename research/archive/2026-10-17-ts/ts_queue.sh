#!/bin/bash
# The one launcher for TS (setup_triple_screen) alone: March 2026, XAUUSD, TS-w / TS-r on M15 and M5.
# Starts a run only when both checks see fewer than 4 backtests in total (the OOS queue of the other session
# counts these too and starts its own only below 3).
cd /c/Users/korap/taa
OUT=data/backtests/ts
RUNS=${RUNS:-"ts_w_m15 ts_r_m15 ts_w_m5 ts_r_m5"}
START=${START:-2026-03-01}; END=${END:-2026-04-01}; TAG=${TAG:-2026-03}; SYMS=${SYMS:-XAUUSD}
live() {
  powershell -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*.venv*app.cli backtest*' }).Count" | tr -d '\r'
}
for v in $RUNS; do
  log=$OUT/${v}_$TAG.log
  grep -q expectancy "$log" 2>/dev/null && continue
  while true; do
    a=$(live); sleep 2; b=$(live)
    [ "${a:-9}" -lt 4 ] && [ "${b:-9}" -lt 4 ] && break
    sleep 20
  done
  echo "$(date +%H:%M) start ${v}_$TAG"
  CONFIG_FILE=data/research/config_$v.yaml ENABLE_HIGH_RISK_PROFILE=false MAX_ACCOUNT_DRAWDOWN_PERCENT=50 ALLOWED_SYMBOLS=$SYMS \
  PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python -m app.cli backtest --server FBS-Demo --symbols $SYMS \
    --start $START --end $END --strategies setup_triple_screen --out $OUT/${v}_$TAG --progress > "$log" 2>&1 &
  sleep 15
done
wait
echo "$(date +%H:%M) queue done"
