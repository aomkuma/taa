# Session handoff

Last updated: 2026-10-03, at the end of Phase 2. This file holds **state only**. Rules and conventions live in
`CLAUDE.md` (loaded automatically by Claude Code) and `docs/CODING_STANDARDS.md`.

---

## Prompt for the next session

Paste this into a new Claude Code session opened in `C:\Users\korap\taa`:

```text
Continue the TAA project. Read docs/HANDOFF.md (state), docs/TICKETS.md (progress + execution order) and the
relevant sections of docs/PLAN.md. Follow CLAUDE.md and docs/CODING_STANDARDS.md.
Phases 0, 1 and 2 are DONE. Next: Phase 2A (TAA-2A1..2A9 evidence engine), then continue in the execution
order 2A -> 3 -> 4 -> 5 -> 6 -> 6A -> 6B -> 6C -> 7 -> 8 -> 8A -> 9 -> 10 -> 11.
Tick the checklist after each item. Stop for review at the end of Milestone 1, or at any phase boundary if I ask.
```

---

## Current state

- **Done:** Phase 0 (TAA-001..009), Phase 1 (TAA-101..110) and Phase 2 (TAA-201..206).
- **Checks:** 310 tests pass, 8 skipped (real-terminal, Postgres, one contract case defined from bar 0). ruff,
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
  - a local `.env` (git-ignored) with the FBS **demo** login and random `ENGINE_ID`, `ENGINE_HMAC_SECRET` and
    `CONTROL_TOTP_SECRET`. It uses the master password with `PAPER_ALLOW_MASTER_PASSWORD=true` (the user's
    choice for the demo account). Blank env values count as unset (`env_ignore_empty`).
  - the bot terminal is a dedicated portable copy at `C:\MT5	aa-bot` (option A in `.env`); option B, the
    installed terminal, is commented out.
  - real terminal verified: `doctor` reports 0 failures (warnings: master password, Algo Trading button off,
    market idle on the weekend), and `pytest -m mt5` passes 6/6. Demo account: USD, 1:200, hedging. A fresh
    terminal may need a moment to sync a symbol before `order_calc_profit` works (XAUUSD failed once on the
    first run).
- **Git:** `main`, first commit `7d2ab1a` (Phases 0–2). No remote yet.
- **Next step:** Phase 2A, starting with TAA-2A1 (evidence framework).

## Open items needing the user

- Whether and when to push to GitHub (no remote configured).
- Before Phase 11: Railway account access for deployment (only with explicit go-ahead).
- Before ever enabling subscriptions: legal review (Thai SEC advisory licensing, PDPA). See PLAN §A30.
