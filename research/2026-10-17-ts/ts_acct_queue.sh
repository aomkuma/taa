#!/bin/bash
# TS on the owner's account terms: 100 USD, leverage 1:2000 (config_ts_n3c_acct.yaml), the aggressive preset at
# 7.5 % a trade (the cage of config.yaml: min lot up to 15 % risk, 4 losses in a row pause 24 h, kill at 60 % DD).
# The real .env (no research overrides), one run at a time below 4 backtests in total.
cd /c/Users/korap/taa
OUT=data/backtests/ts
live() {
  powershell -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*.venv*app.cli backtest*' }).Count" | tr -d '\r'
}
for span in "2026-03-01 2026-04-01 2026-03" "2026-08-01 2026-09-01 2026-08"; do
  set -- $span
  log=$OUT/acct_n3c_$3.log
  grep -q expectancy "$log" 2>/dev/null && continue
  while true; do a=$(live); sleep 2; b=$(live); [ "${a:-9}" -lt 4 ] && [ "${b:-9}" -lt 4 ] && break; sleep 20; done
  echo "$(date +%H:%M) start acct_n3c_$3"
  CONFIG_FILE=data/research/config_ts_n3c_acct.yaml ALLOWED_SYMBOLS=XAUUSD PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
  .venv/Scripts/python -m app.cli backtest --server FBS-Demo --symbols XAUUSD --start $1 --end $2 \
    --strategies setup_triple_screen --balance 100 --preset aggressive --risk 7.5 --out $OUT/acct_n3c_$3 --progress > "$log" 2>&1
done
echo "$(date +%H:%M) acct queue done"
