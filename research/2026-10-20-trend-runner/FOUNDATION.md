# TR1 foundation report

Measured: 2026-10-20 13:58 Thai time (06:58 UTC). This report reads P1 only. No P2 or exam row or tick file was
opened.

## Commands

```powershell
.venv\Scripts\python -m pytest research\2026-10-20-trend-runner\tests -q
.venv\Scripts\ruff format --check research\2026-10-20-trend-runner
.venv\Scripts\ruff check research\2026-10-20-trend-runner
.venv\Scripts\python research\2026-10-20-trend-runner\foundation_report.py
.venv\Scripts\python research\2026-10-20-trend-runner\plant_foundation.py
```

## Data manifest

P1 is `[2025-10-18 00:00 UTC, 2026-01-16 00:00 UTC)`. The first gold M1 row is Sunday 2025-10-19 22:05 UTC because
the period begins on a weekend.

- M1: 84,358 rows; first 2025-10-19 22:05 UTC; last 2026-01-15 23:59 UTC.
- M1 duplicate timestamps: 0.
- M1 gaps over one minute: 67; the largest is 3,155 minutes. This count includes scheduled market closures and does
  not label a closure as a data fault.
- Ticks: 64 UTC-day files, 22,567,497 rows; first 2025-10-20 00:00:00.010 UTC; last
  2026-01-15 23:59:58.956 UTC.
- Tick rows sharing a timestamp: 19,025. They are preserved in stable file order because separate quotes can arrive
  within the same recorded millisecond.
- Crossed bid/ask quotes: 0.
- Latest tick file opened: 2026-01-15. The P2 and exam guards fail before attempting a filesystem read.

## Derived bars against broker bars

Bars were derived independently from M1 on UTC clock boundaries. Availability is the clock end of the bar, not the
last observed M1 row.

| Timeframe | Matched bars | Only derived | Only broker | Maximum OHLC difference | Differing values |
|---|---:|---:|---:|---:|---:|
| M5 | 16,876 | 0 | 0 | 0.0 | 0 |
| M15 | 5,668 | 0 | 0 | 0.0 | 0 |
| H1 | 1,418 | 0 | 0 | 0.0 | 0 |

## Tests and planted bugs

- Foundation unit tests: 30 passed at this checkpoint.
- Ruff format/check: clean.
- Planted bugs: 14 of 14 caught.

The planted faults include unlocking P2/exam, including the period end, opening a forbidden tick file, crossing a
period boundary, dropping same-millisecond quotes, exposing a bar or pivot early, changing ATR, buying at the bid,
ignoring an entry gap, booking a gap stop at the stop price, booking a target at an improved market price and delaying
a time exit.

## Decisions fixed by this checkpoint

- Tick sequence is non-decreasing, not necessarily unique. File order breaks ties.
- Entry pays the adverse side of the spread and any explicit non-negative slippage.
- A stop gap fills at the first worse quote; a profit target is booked at the declared target.
- An exit at a clock time uses the first quote at or after that time.
- Stops never receive a favourable fill merely because the stop price was crossed in a gap.

The next checkpoint is the P1-only opportunity study. Its exact impulse and pullback measurements must be written
before they are computed.
