#!/bin/bash
# S1 with the spread floor (min_atr_spreads 15, time stop 240) against S1 as it is, in the engine, one month a run
# (owner, 2026-10-17: "the spread must not be what stops the trades; find it and fix it"). The floor runs on the
# fix's code (worktree s1-cost-floor), the baselines S1 lacks on the frozen code of the out-of-sample runs.
# One launcher; a run starts only while fewer than 4 backtests run on the machine (both checks).
MAIN=/c/Users/korap/taa
OUT=$MAIN/data/backtests/s1fix
FIX=$MAIN/.claude/worktrees/s1-cost-floor
FROZEN=$MAIN/.claude/worktrees/oos-runner
mkdir -p "$OUT"
JOBS="floor:2026-03 floor:2026-08 floor:2024-10 floor:2024-11 floor:2024-12 base:2024-03 floor:2024-03 base:2024-08 floor:2024-08"
procs() {
  powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*.venv*app.cli backtest*' } | ForEach-Object { (\$_.CommandLine -split '--out ')[1].Split(' ')[0] }" | tr -d '\r'
}
run() {  # variant month
  local v=$1 m=$2 y mo end code cfg
  y=${m%-*}; mo=$((10#${m#*-} + 1)); [ $mo -eq 13 ] && { mo=1; y=$((y + 1)); }; end=$(printf "%04d-%02d-01" $y $mo)
  if [ "$v" = floor ]; then code=$FIX; cfg=config_s1_floor; else code=$FROZEN; cfg=config_scalp_s1; fi
  cd "$code" || return
  CONFIG_FILE=$MAIN/data/research/$cfg.yaml ENABLE_HIGH_RISK_PROFILE=false MAX_ACCOUNT_DRAWDOWN_PERCENT=50 \
  ALLOWED_SYMBOLS=XAUUSD PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 $MAIN/.venv/Scripts/python -m app.cli backtest \
    --server FBS-Demo --data $MAIN/data/history --symbols XAUUSD --start $m-01 --end $end --strategies setup_breakout \
    --out $OUT/${v}_$m --progress > "$OUT/${v}_$m.log" 2>&1
}
for job in $JOBS; do
  v=${job%%:*}; m=${job#*:}
  grep -q expectancy "$OUT/${v}_$m.log" 2>/dev/null && continue
  procs | grep -q "${v}_$m\$" && continue
  while true; do
    a=$(procs | grep -c .); sleep 2; b=$(procs | grep -c .)
    [ "$a" -lt 4 ] && [ "$b" -lt 4 ] && break
    sleep 30
  done
  echo "$(date +%H:%M) start ${v}_$m"
  run "$v" "$m" &
  sleep 20
done
wait
echo "$(date +%H:%M) queue done"
