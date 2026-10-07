#!/usr/bin/env bash
# One-year advisory replay of one family of setups, per symbol in parallel, each into its own scratch database.
# usage: [SYMBOLS="EURUSD GBPUSD"] run_family.sh NAME STRATEGIES DETECTORS [CONFIG]  (two at a time for the chart detectors)
cd "$(dirname "$0")/../.." || exit 1
S="$(pwd)/data/research"
W="$(cygpath -m "$(pwd)")/data/research"
NAME=$1 STRATS=$2 DET=$3 CONFIG=${4:-config.yaml}
for SYM in ${SYMBOLS:-EURUSD GBPUSD USDJPY XAUUSD}; do
  rm -f "$S/fam_${NAME}_$SYM.db"; mkdir -p "$S"
  ENGINE_DB_URL="sqlite:///$W/fam_${NAME}_$SYM.db" TRADING_MODE=PAPER \
    .venv/Scripts/python -m app.cli --config "$CONFIG" advisory replay --server FBS-Demo --symbols "$SYM" \
    --start 2025-10-15 --end 2026-10-05 --strategies "$STRATS" --detectors "$DET" --progress \
    > "$S/fam_${NAME}_$SYM.log" 2>&1 &
done
wait
echo "family $NAME finished at $(date -u)"
tail -n 3 "$S"/fam_"${NAME}"_*.log
