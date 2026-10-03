# Session handoff

Last updated: 2026-10-03, during Phase 2A (TAA-2A1..2A6 done, TAA-2A10 in progress). This file holds **state
only**. Rules and conventions live in `CLAUDE.md` (loaded automatically by Claude Code) and
`docs/CODING_STANDARDS.md`.

---

## Prompt for the next session

Paste this into a new Claude Code session opened in `C:\Users\korap\taa`:

```text
Continue the TAA project. Read docs/HANDOFF.md (state), docs/TICKETS.md (progress + execution order) and the
relevant sections of docs/PLAN.md (§A29 evidence engine, §A31 trading profile). Follow CLAUDE.md and
docs/CODING_STANDARDS.md.
Phases 0, 1 and 2 are DONE; Phase 2A is DONE up to TAA-2A6. First finish TAA-2A10 (work in progress, see
"In progress" in HANDOFF), then TAA-2A7 (harmonics), 2A8 (Elliott), 2A9 (selective computation), then continue
in the execution order 3 -> 4 -> 5 -> 6 -> 6A -> 6B -> 6C -> 7 -> 8 -> 8A -> 9 -> 10 -> 11.
Commit at each ticket boundary (allowed); ask before pushing. Stop for review at the end of Milestone 1, or at
any phase boundary if I ask.
```

---

## In progress: TAA-2A10 (Fibonacci extension levels & candle location)

Approved plan (rev. 3). The user asked whether a shooting star at resistance or at the Fibonacci 161.8 /
261.8 / 423.6 % extensions counts for more; this ticket adds that.

- **Done, uncommitted:** `FibExtensionLevel` (`fib.extension_level`) in `app/evidence/fibonacci.py`. It has
  two-point (`A + r·AB`) and trend-based (`C + r·AB`) levels for ratios 1.272 / 1.618 / 2.618 / 4.236, and
  reports a rejection against the leg, once per level. A leg's levels stay in force until the next
  same-direction extreme D is confirmed (`pivots[i + 3].confirm_pos`); a close beyond A ends them. ruff and mypy
  are clean. It is **not registered or tested yet**.
- **Remaining:**
  1. Register `FibExtensionLevel()` in `app/evidence/catalog.py`, so the look-ahead harness runs on it.
  2. In `app/evidence/candlesticks.py`:
     - Make `LOCATION_SOURCES` hold (detector id, variant filter) pairs.
     - Add `fib.extension_level`, `fib.cluster` and `structure.trendline` (bounce variants only).
     - Keep `depends_on` a tuple of ids.
     - Make `_level_hits` return the matching evidence keys per (bar, direction) and add the detail `at_levels`
       (comma-joined, sorted i18n keys).
     - Keep the quality formula `0.6 + 0.4 × at_level`.
  3. Tests:
     - golden: external 161.8 % and projection 261.8 % (use `tests/evidence_paths.path`)
     - near-miss: closing through the level does not count
     - a shooting star at the 161.8 % extension has `at_level=True` and `at_levels` containing
       `evidence.fib.extension_level.external.161.8`
     - the existing location test in `tests/unit/test_evidence_candlesticks.py` stubs `LOCATION_SOURCES` by id;
       update it for the new tuple shape
  4. Add the detector row to `docs/PATTERNS.md` (Fibonacci table) and update the candlestick location bullet.
  5. Run all gates, tick TAA-2A10 (`scripts/tickets.py tick TAA-2A10 1 2 3 4 5` + `sync`), and commit.

## Current state

- **Done:** Phase 0 (TAA-001..009), Phase 1 (TAA-101..110), Phase 2 (TAA-201..206) and TAA-2A1..2A6.
- **Checks:** 574 tests pass, 8 skipped (real-terminal, Postgres, one contract case defined from bar 0). ruff,
  mypy and bandit are clean. Architecture rules are enforced by `tests/unit/test_architecture.py`.
- **Design rev. 3** (committed docs, code later in its phases):
  - PLAN §A31 "Trading profile & entry plans":
    - style slider 0–100 (defensive → offensive) with five anchor presets
    - risk per signal (all entries) and portfolio heat
    - entry splitting: `SINGLE`, `SAME_PRICE` with staggered TPs, `SCALE_IN` with a shared stop
    - lot per tap (`lot_unit`); lots computed from the risk budget, never rounded up
    - M2 limits = min(profile, local `RiskConfig`)
  - The user's choices: all three split modes, lots computed from the budget, both risk budgets (per signal
    and portfolio). Item 1 was to be built now; item 2 follows the phase order.
  - Ticket items marked "(rev. 3)": TAA-401, 402, 406, 6B1, 8A4, 810, and the new TAA-922 (Phase 9).
- **Built:**
  - config (pydantic-settings + `config.yaml`, percent risk units, hard ceilings)
  - secrets (`keyring:` indirection, log redaction), JSON logging
  - SQLite/Postgres storage with Alembic (migrations 0001, 0002), hash-chained audit log
  - kill switch; CLI (`config`, `db`, `audit`, `kill`, `doctor`); CI config
  - read-only MT5 client and gateway (explicit login, account verification, order functions blocked,
    `symbols(group)`, `ticks_range`)
  - multi-asset FakeMT5 (schedules, ticks, fixed and FBS-tiered leverage)
  - ServerClock (FBS = EET, `Europe/Athens`)
  - closed-candle service with watermarks, quality checks, quote service
  - history store (Parquet/SQL) and downloader
  - indicators (`app/indicators/`): trend, momentum, volatility, tick-volume features, and price action
    (candle anatomy, confirmed swings, structure, S/R zones, breakouts). Formulas, warm-up positions and TA-Lib
    differences are in `docs/INDICATORS.md`. Every indicator is registered in
    `tests/unit/test_indicators_contract.py` (warm-up, look-ahead and short-input checks).
  - evidence engine (`app/evidence/`, PLAN §A29):
    - framework, multi-degree zigzag, registry with prerequisite closure, look-ahead harness
    - 52 registered detectors: Fibonacci, levels, chart patterns, candlesticks, momentum, trend,
      volatility/volume, sessions, Ichimoku, structure, smart money
    - catalog and rules in `docs/PATTERNS.md`; every detector must be documented there and pass the harness
      (`tests/unit/test_evidence_catalog.py`)
    - test helpers: `tests/evidence_harness.py` (harness, `scan_one`) and `tests/evidence_paths.py` (`path` =
      straight legs between vertices, `bars` = explicit OHLC rows)
  - a local `.env` (git-ignored) with the FBS **demo** login and random `ENGINE_ID`, `ENGINE_HMAC_SECRET` and
    `CONTROL_TOTP_SECRET`. It uses the master password with `PAPER_ALLOW_MASTER_PASSWORD=true` (the user's
    choice for the demo account). Blank env values count as unset (`env_ignore_empty`).
  - the bot terminal is a dedicated portable copy at `C:\MT5\taa-bot` (option A in `.env`); option B, the
    installed terminal, is commented out.
  - real terminal verified:
    - `doctor` reports 0 failures (warnings: master password, Algo Trading button off), and `pytest -m mt5`
      passes 6/6
    - server time is verified even on weekends through 24/7 crypto symbols (`symbols.clock_fallback_symbols`,
      default BTCUSD/ETHUSD); FBS offset +3h (EEST) confirmed
    - demo account: USD, 1:200, hedging
    - a fresh terminal may need a moment to sync a symbol before `order_calc_profit` works (XAUUSD failed once
      on the first run)
  - the demo account also carries a manual BTCUSD test position (magic 0). Per PLAN, manual positions count
    toward exposure (policy: count or halt), and Phase 6B uses them to detect FOLLOWED opportunities.
- **Git:** `main`, committed per ticket (the user allows commits at ticket boundaries; ask before pushing). No
  remote yet. The TAA-2A10 code in `app/evidence/fibonacci.py` is the only uncommitted change.
- **Next step:** finish TAA-2A10 (above), then TAA-2A7 (harmonic patterns).

## Notes for the next session

- Docstrings longer than 110 characters fail ruff (E501). Wrap them by hand, or keep the summary line short and
  put the details in a paragraph below it.
- `docs/TICKETS.md` uses CRLF line endings. `scripts/tickets.py` handles that; if you edit the file by hand,
  preserve the line endings.
- The catalog test is the slowest part of the suite (~15 s), because candlestick detectors run their location
  prerequisites.

## Open items needing the user

- Whether and when to push to GitHub (no remote configured).
- Before Phase 11: Railway account access for deployment (only with explicit go-ahead).
- Before ever enabling subscriptions: legal review (Thai SEC advisory licensing, PDPA). See PLAN §A30.
