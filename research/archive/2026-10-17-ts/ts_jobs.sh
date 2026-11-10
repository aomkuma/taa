#!/bin/bash
# Runs the jobs of a list file (name|CONFIG_FILE stem|extra env|backtest args), each when fewer than 4 backtests
# run machine-wide and fewer than MAX of these. Outputs and logs in data/backtests/ts/jobs/.
cd /c/Users/korap/taa
OUT=data/backtests/ts/jobs; MAX=${MAX:-2}; TAG=${TAG:-jobs}
live() {
  powershell -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*.venv*app.cli backtest*' }).Count" | tr -d '\r'
}
mine() {
  powershell -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*.venv*app.cli backtest*' -and \$_.CommandLine -like '*backtests/ts/jobs*' }).Count" | tr -d '\r'
}
while IFS='|' read -r name cfg extra args; do
  [ -z "$name" ] || [ "${name:0:1}" = "#" ] && continue
  grep -q expectancy "$OUT/$name.log" 2>/dev/null && continue
  while true; do a=$(live); sleep 2; b=$(live); c=$(mine)
    [ "${a:-9}" -lt 4 ] && [ "${b:-9}" -lt 4 ] && [ "${c:-9}" -lt "$MAX" ] && break; sleep 20; done
  echo "$(date +%H:%M) start $name"
  env CONFIG_FILE=data/research/$cfg.yaml $extra PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    .venv/Scripts/python -m app.cli backtest --server FBS-Demo $args --out $OUT/$name --progress > "$OUT/$name.log" 2>&1 &
  sleep 15
done < "$1"
wait
echo "$(date +%H:%M) $TAG done"
