# OANDA historical feed acquisition

This read-only downloader prepares a feed-matched M1 dataset for the XAUUSD M5 Volume Profile research. It fetches OANDA v20 M1 candles with midpoint, bid, ask, and OANDA's candle `volume` field (the number of prices created in that interval). It never places orders and never writes the API token to disk.

## Requirements

- An OANDA v20 account and personal REST API token. OANDA's documentation says API access requires a v20 account and a token generated from the Account Management Portal; availability depends on OANDA division.
- Python standard library only. No added packages.
- Set `OANDA_API_TOKEN` in the current PowerShell process. If the token covers multiple accounts, also set `OANDA_ACCOUNT_ID`. Do not paste either credential into chat or commit it into a file.
- `OANDA_ENVIRONMENT` is `practice` by default; use `live` to query the live pricing environment.

## Example (temporary token prompt)

```powershell
$secureToken = Read-Host 'OANDA API token' -AsSecureString
$tokenPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
try {
    $env:OANDA_API_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPtr)
    .venv\Scripts\python.exe research\xauusd_poc_m5\oanda_feed\fetch_candles.py `
        --start 2025-10-01T00:00:00Z `
        --end 2026-10-29T00:00:00Z `
        --environment practice `
        --out research\xauusd_poc_m5\oanda_feed\XAU_USD_M1_2025-10-01_2026-10-28.csv
} finally {
    Remove-Item Env:OANDA_API_TOKEN -ErrorAction SilentlyContinue
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPtr)
}
```

The end timestamp is exclusive. The downloader pages three days at a time (at most 4,320 possible M1 bars per request), skips incomplete candles, de-duplicates boundary timestamps, and writes an adjacent metadata JSON. It refuses to overwrite an existing output file.

## Backtest limits after download

- Use OANDA M1 `volume` with M1 midpoint OHLC to reconstruct the tick-volume profile. This remains an OHLC-based row-allocation approximation to TradingView's indicator.
- Use OANDA bid/ask M1 OHLC for executable-side checks. Historical M1 candles do not preserve the exact order of intraminute events; when both stop and target could have hit in the same M1 candle, score the stop first. This is conservative but not a tick replay.
- OANDA's live pricing stream is not a complete tick tape; official docs state it sends at most four prices per second. New forward collection can still improve quote matching but should be labeled sampled stream data.

## Official references

- [OANDA v20 introduction and account/token setup](https://developer.oanda.com/rest-live-v20/introduction/)
- [OANDA instrument candle fields, granularities, and price-update volume](https://developer.oanda.com/rest-live-v20/instrument-df/)
- [OANDA pricing endpoint, including bid/ask/mid candles and M1 range parameters](https://developer.oanda.com/rest-live-v20/pricing-ep/)

## Normalize after download

After a CSV has been downloaded, convert it to the research engine's M1/M5 parquet shape and produce a coverage audit:

```powershell
.venv\Scripts\python.exe research\xauusd_poc_m5\oanda_feed\prepare_candles.py `
    --input research\xauusd_poc_m5\oanda_feed\XAU_USD_M1_2025-10-01_2026-10-28.csv `
    --out-dir research\xauusd_poc_m5\oanda_feed\normalized_2025-10_2026-10
```

The preparation step preserves M1 midpoint and bid/ask OHLC, maps OANDA price-update count to `tick_volume`, and aggregates only exact groups of five contiguous M1 bars into M5. It writes a session-independent M1/M5 coverage audit; market closures naturally appear as non-contiguous intervals and must not be mistaken for missing active-session data.

## OANDA OCO replay

Once normalization succeeds, run the preconfigured OCO study:

```powershell
.venv\Scripts\python.exe research\xauusd_poc_m5\oanda_feed\backtest_oco_m1.py `
    --data-dir research\xauusd_poc_m5\oanda_feed\normalized_2025-10_2026-10 `
    --out-dir research\xauusd_poc_m5\oanda_feed\oco_m1_2025-10_2026-10
```

The engine compares three fixed variants: base VAL/VAH OCO, stationary POC drift <=$0.50, and stationary POC drift <=$1.00 (the two stable variants also require a prior close inside value and six-hour efficiency <=0.25). It uses the same historical session time windows as the FBS study, but decides session inclusion from OANDA M5 coverage; it then splits OANDA-covered sessions chronologically 70/30 and computes three development folds.

M1 bid/ask candles are the execution source: limit fills occur at the limit if the relevant M1 quote extreme touches it, with no price improvement; stops fill at the stop or a worse M1 open; if stop and target are both touched in one M1 candle, stop wins. This is conservative about event order but cannot model passive queue position or exact intraminute fills. Use results as a historical candle replay, not tick-exact execution.

The exact preset rules and execution assumptions for `backtest_oco_m1.py` are in [`BACKTEST_PROTOCOL.md`](BACKTEST_PROTOCOL.md). The engine source was syntax-compiled, but no backtest has been run because no OANDA dataset or API token is present.
