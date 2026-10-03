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
  - a local `.env` (git-ignored) generated from `.env.example`, with random `ENGINE_ID`, `ENGINE_HMAC_SECRET`
    and `CONTROL_TOTP_SECRET`. The MT5 credentials are still placeholders. Blank env values now count as unset
    (`env_ignore_empty`), so the template's empty lines load.
- **Git:** initialized on `main`; **nothing committed yet**.
- **Next step:** Phase 2A, starting with TAA-2A1 (evidence framework).

## Open items needing the user

- Fill the MT5 placeholders in `.env` (`MT5_LOGIN`, `MT5_PASSWORD` = the FBS **investor** read-only password,
  `MT5_SERVER`, `MT5_TERMINAL_PATH`) so `python -m app.cli doctor` can run against the real terminal. The real-terminal contract tests run with `TAA_MT5_TESTS=1`.
- Whether and when to make the first git commit / push to GitHub.
- Before Phase 11: Railway account access for deployment (only with explicit go-ahead).
- Before ever enabling subscriptions: legal review (Thai SEC advisory licensing, PDPA). See PLAN §A30.
