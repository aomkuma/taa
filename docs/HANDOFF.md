# Session handoff

Last updated: 2026-10-03, during Phase 2A (TAA-2A1..2A6 done). This file holds **state only**. Rules and conventions live in
`CLAUDE.md` (loaded automatically by Claude Code) and `docs/CODING_STANDARDS.md`.

---

## Prompt for the next session

Paste this into a new Claude Code session opened in `C:\Users\korap\taa`:

```text
Continue the TAA project. Read docs/HANDOFF.md (state), docs/TICKETS.md (progress + execution order) and the
relevant sections of docs/PLAN.md. Follow CLAUDE.md and docs/CODING_STANDARDS.md.
Phases 0, 1 and 2 are DONE; Phase 2A is DONE up to TAA-2A6. Next: TAA-2A7 (harmonics), 2A8 (Elliott), 2A9
(selective computation), then continue in the execution order 3 -> 4 -> 5 -> 6 -> 6A -> 6B -> 6C -> 7 -> 8 ->
8A -> 9 -> 10 -> 11.
Tick the checklist after each item. Stop for review at the end of Milestone 1, or at any phase boundary if I ask.
```

---

## Current state

- **Done:** Phase 0 (TAA-001..009), Phase 1 (TAA-101..110), Phase 2 (TAA-201..206) and TAA-2A1..2A6.
- **Checks:** 574 tests pass, 8 skipped (real-terminal, Postgres, one contract case defined from bar 0). ruff,
  mypy and bandit are clean.
  Architecture rules are enforced by `tests/unit/test_architecture.py`.
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
  - evidence engine (`app/evidence/`, PLAN §A29): framework, multi-degree zigzag, registry with prerequisite
    closure, look-ahead harness, and 52 detectors (Fibonacci, levels, chart patterns, candlesticks, momentum,
    trend, volatility/volume, sessions, Ichimoku, structure, smart money). Catalog and rules: `docs/PATTERNS.md`.
    Every detector must be documented there and pass the harness (`tests/unit/test_evidence_catalog.py`).
  - a local `.env` (git-ignored) with the FBS **demo** login and random `ENGINE_ID`, `ENGINE_HMAC_SECRET` and
    `CONTROL_TOTP_SECRET`. It uses the master password with `PAPER_ALLOW_MASTER_PASSWORD=true` (the user's
    choice for the demo account). Blank env values count as unset (`env_ignore_empty`).
  - the bot terminal is a dedicated portable copy at `C:\MT5	aa-bot` (option A in `.env`); option B, the
    installed terminal, is commented out.
  - real terminal verified: `doctor` reports 0 failures (warnings: master password, Algo Trading button off),
    and `pytest -m mt5` passes 6/6. Server time is verified even on weekends through 24/7 crypto symbols
    (`symbols.clock_fallback_symbols`, default BTCUSD/ETHUSD; FBS offset +3h = EEST confirmed). Demo account: USD, 1:200, hedging. A fresh
    terminal may need a moment to sync a symbol before `order_calc_profit` works (XAUUSD failed once on the
    first run).
  - the demo account also carries a manual BTCUSD test position (magic 0). Per PLAN, manual positions count
    toward exposure (policy: count or halt), and Phase 6B uses them to detect FOLLOWED opportunities.
- **Git:** `main`, committed per ticket (the user allows commits at ticket boundaries; ask before pushing). No
  remote yet.
- **Next step:** TAA-2A7 (harmonic patterns).

## Open items needing the user

- Whether and when to push to GitHub (no remote configured).
- Before Phase 11: Railway account access for deployment (only with explicit go-ahead).
- Before ever enabling subscriptions: legal review (Thai SEC advisory licensing, PDPA). See PLAN §A30.
