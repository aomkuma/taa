# Session handoff

Last updated: 2026-10-03, during Phase 2A (TAA-2A1..2A6 and TAA-2A10 done). This file holds **state
only**. Rules and conventions live in `CLAUDE.md` (loaded automatically by Claude Code) and
`docs/CODING_STANDARDS.md`.

---

## Prompt for the next session

Paste this into a new Claude Code session opened in `C:\Users\korap\taa`:

```text
Continue the TAA project. Read docs/HANDOFF.md (state), docs/TICKETS.md (progress + execution order) and the
relevant sections of docs/PLAN.md (§A29 evidence engine, §A31 trading profile). Follow CLAUDE.md and
docs/CODING_STANDARDS.md.
Phases 0, 1 and 2 are DONE; in Phase 2A, TAA-2A1..2A6 and 2A10 are DONE. Next: TAA-2A7 (harmonics), 2A8
(Elliott), 2A9 (selective computation), then continue in the execution order
3 -> 4 -> 5 -> 6 -> 6A -> 6B -> 6C -> 7 -> 8 -> 8A -> 9 -> 10 -> 11.
Commit at each ticket boundary (allowed); ask before pushing. Stop for review at the end of Milestone 1, or at
any phase boundary if I ask.
```

---

## Current state

- **Done:** Phase 0 (TAA-001..009), Phase 1 (TAA-101..110), Phase 2 (TAA-201..206), TAA-2A1..2A6 and
  TAA-2A10.
- **Checks:** 589 tests pass, 8 skipped (real-terminal, Postgres, one contract case defined from bar 0). ruff,
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
    - 53 registered detectors: Fibonacci, levels, chart patterns, candlesticks, momentum, trend,
      volatility/volume, sessions, Ichimoku, structure, smart money
    - (rev. 3, TAA-2A10) `fib.extension_level`: 127.2/161.8/261.8/423.6 % extensions as support/resistance
      (two-point and trend-based). Candle location sources now include it, `fib.cluster` and trendline
      bounces; breaks don't count (`prev_high_low` uses `reject` variants only). Candle records carry
      `at_levels` (the i18n keys of the levels they sat on).
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
  remote yet. The working tree is clean.
- **Next step:** TAA-2A7 (harmonic patterns), then 2A8 (Elliott) and 2A9 (selective computation).

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
