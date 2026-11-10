#!/bin/bash
# The TS trigger datasets (in-sample year 2025-10 .. 2026-09), one at a time, below 4 backtests in total.
cd /c/Users/korap/taa
OUT=data/backtests/ts
live() {
  powershell -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*.venv*app.cli backtest*' }).Count" | tr -d '\r'
}
for tf in ${TFS:-m15}; do
  [ -f "$OUT/dataset_$tf/triggers.csv" ] && continue
  while true; do a=$(live); sleep 2; b=$(live); [ "${a:-9}" -lt 4 ] && [ "${b:-9}" -lt 4 ] && break; sleep 20; done
  echo "$(date +%H:%M) start dataset_$tf"
  CONFIG_FILE=data/research/config_ts_all_$tf.yaml ENABLE_HIGH_RISK_PROFILE=false MAX_ACCOUNT_DRAWDOWN_PERCENT=50 ALLOWED_SYMBOLS=XAUUSD \
  PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python -X utf8 research/2026-10-17-ts/ts_dataset.py app.cli backtest \
    --server FBS-Demo --symbols XAUUSD --start ${START:-2025-10-01} --end ${END:-2026-10-01} --strategies setup_triple_screen \
    --out $OUT/dataset_$tf --progress > $OUT/dataset_$tf.log 2>&1
  echo "$(date +%H:%M) done dataset_$tf: $(tail -2 $OUT/dataset_$tf.log | head -1)"
done
