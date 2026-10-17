#!/bin/bash
# Year C trigger dataset first (the hold-out for the behaviour rules), then the TS-h4 months, then TS-h4 on the 8.
cd /c/Users/korap/taa
live() { powershell -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*.venv*app.cli backtest*' }).Count" | tr -d '\r'; }
if [ ! -f data/backtests/ts/c_dataset_m15/triggers.csv ]; then
  while true; do a=$(live); sleep 2; b=$(live); [ "${a:-9}" -lt 4 ] && [ "${b:-9}" -lt 4 ] && break; sleep 20; done
  echo "$(date +%H:%M) start c_dataset_m15"
  CONFIG_FILE=data/research/config_ts_all_m15.yaml ENABLE_HIGH_RISK_PROFILE=false MAX_ACCOUNT_DRAWDOWN_PERCENT=50 ALLOWED_SYMBOLS=XAUUSD \
  PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python -X utf8 research/2026-10-17-ts/ts_dataset.py app.cli backtest \
    --server FBS-Demo --symbols XAUUSD --start 2023-10-01 --end 2024-10-01 --strategies setup_triple_screen \
    --out data/backtests/ts/c_dataset_m15 --progress > data/backtests/ts/c_dataset_m15.log 2>&1
  echo "$(date +%H:%M) done c_dataset_m15: $(grep '^triggers:' data/backtests/ts/c_dataset_m15.log)"
fi
OUT=data/backtests/ts/h4 CFG=config_ts_h4_m15 bash research/2026-10-17-ts/ts_month_queue.sh >> data/backtests/ts/h4/queue.log 2>&1
MAX=1 TAG=list3 bash research/2026-10-17-ts/ts_jobs.sh data/backtests/ts/jobs/list3.txt > data/backtests/ts/jobs/list3.log 2>&1
echo "$(date +%H:%M) chain done"
