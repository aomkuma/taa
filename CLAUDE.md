# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

TAA is an automated trading platform for an FBS account via MetaTrader 5. A Python **engine** runs on Windows next to
the MT5 terminal (the `MetaTrader5` package is Windows-only). A FastAPI **web** service (API + React PWA), a
**worker** and PostgreSQL run on Railway. The design favors capital protection, fail-closed behavior and
auditability over features. No profitability claims anywhere.

Read before larger work:
- `docs/PLAN.md`: design, revision 5. Section numbers run A1–A21, then A25–A33, then A22–A24.
- `docs/TICKETS.md`: tickets, checklists, progress table and execution order.
- `docs/HANDOFF.md`: current state and open items.
- `docs/CODING_STANDARDS.md`: detailed coding conventions. **Follow them.**

## Commands (Windows, run from the repo root; always use the venv)

```powershell
.venv\Scripts\python -m pip install -r requirements.txt -r requirements/dev.txt   # setup
.venv\Scripts\python -m pytest -q                                   # all tests
.venv\Scripts\python -m pytest tests/unit/test_broker.py::TestConnection::test_reconnect_with_backoff -q  # one test
.venv\Scripts\python -m pytest -m mt5      # real-terminal contract tests (also needs TAA_MT5_TESTS=1 and a .env)
.venv\Scripts\python -m pytest -m postgres # local PostgreSQL 16; TAA_POSTGRES_URL in .env (role taa)
.venv\Scripts\ruff format app tests scripts; .venv\Scripts\ruff check app tests scripts
.venv\Scripts\mypy app
.venv\Scripts\bandit -q -r app -c pyproject.toml
.venv\Scripts\python -m app.cli doctor --fake        # diagnostics against FakeMT5 (drop --fake for the real terminal)
.venv\Scripts\python -m app.cli config show | kill --reason "..." | audit verify | db upgrade
.venv\Scripts\python -m app.cli backtest --server FBS-Demo --symbols EURUSD --start 2026-01-01 --end 2026-09-30   # needs data/history
.venv\Scripts\python -m app.main --mode paper [--fake]   # PAPER engine; health: http://127.0.0.1:8765/health
.venv\Scripts\python -m app.main --mode demo   # DEMO broker orders (ENABLE_DEMO_TRADING); see docs/RUNBOOK_DEMO.md
.venv\Scripts\python -m app.cli breaker list | breaker reset NAME --reason "..." | demo-report --days 14
.venv\Scripts\python -m app.cli sync upload-history [--send]   # local Parquet history → cloud (TAA-706)
.venv\Scripts\python -m app.cli web engine add --owner NAME --label X | rotate ID | revoke ID --confirm ID | list | import-env --owner NAME
.venv\Scripts\python -m app.web     # API + built PWA on 127.0.0.1:8000 (needs WEB_ENV/WEB_SESSION_SECRET)
scripts\start-demo.cmd                # local demo: web + worker + FakeMT5 PAPER engine (once: start-demo.ps1 -Setup -Owner NAME)
.venv\Scripts\python -m app.cli web create-user NAME | reset-password NAME | reset-totp NAME | list-users   # web users + TOTP
.venv\Scripts\python scripts\tickets.py tick TAA-201 1 2   # tick checklist items; then:
.venv\Scripts\python scripts\tickets.py sync               # recompute statuses + progress table
```

New tables: add the model under `app/storage/models/` and export it from `app/storage/models/__init__.py`. Then
delete `data/dev-migrations.db`, run `.venv\Scripts\alembic upgrade head`, then
`.venv\Scripts\alembic revision --autogenerate -m "..." --rev-id 000N`, and review the generated file.

A ticket is DONE only when tests, ruff (format + check), mypy and bandit are all green.

Frontend (PWA, `frontend/`, run from that folder; Node ≥ 22; details in `frontend/README.md`):

```powershell
npm install; npm run dev        # http://127.0.0.1:5173, proxies /api to FastAPI on 127.0.0.1:8000
npm run lint; npm run typecheck; npm run test; npm run build   # all four green = frontend ticket DONE
```

## Architecture (big picture)

- **Dependency direction:** `core` → `config` / `security` → `storage` → `broker` (gateway protocol) →
  `market_data` → `indicators` / `evidence` → `strategy` → `risk` / `engine` (decision) → `execution`. Cloud side:
  `sync` → `web` / `worker`; `advisory` and `analytics` are shared libraries.
  - This is **enforced** by `tests/unit/test_architecture.py`: the layer table, MetaTrader5 only in `app/broker`,
    no live-broker imports in web/worker, order functions only in `app/broker`, no direct wall-clock reads.
  - A new package must be added to its `LAYERS` table.
- **Broker access only through `app/broker/gateway.py`:**
  - The `MarketDataGateway` protocol, implemented by `ReadOnlyMT5Gateway` over `MT5Client`.
  - Nothing outside `app/broker/` imports `MetaTrader5`.
  - `MT5Client.call` refuses `order_send` / `order_check` unless `allow_trading=True`, which is only possible in
    DEMO/LIVE. Broker orders go only through `app/broker/execution.py` (`ExecutionGateway`), which accepts
    **DEMO only** (Phase 12 was pulled forward; LIVE waits for Phase 14). PAPER never sends broker orders.
- **Time:** MT5 returns bar/tick/deal epochs in **broker server wall-clock time** (FBS = EET, `Europe/Athens`),
  not UTC. Convert only via `ServerClock` (`app/core/clock.py`). Internally everything is timezone-aware UTC;
  history queries widen the window by ±1 day, then filter.
- **Closed candles only:** `CandleService` drops the forming bar (with a grace period). `CandleWatermarks`
  (persisted) guarantees each bar is evaluated once, even across restarts. Indicators and detectors must never look
  ahead.
- **State ownership:**
  - The engine's local SQLite (`data/taa_engine.db`, WAL, synchronous=FULL) is authoritative for trading state.
  - The cloud Postgres (database `taa`) is a replica plus a command queue, fed by an HMAC-signed outbox.
  - One SQLAlchemy model set and one Alembic history serve both databases, so keep types portable
    (`UTCDateTime`, `JSONType`).
- **Safety primitives:**
  - Hash-chained audit log (`app/storage/audit.py`, chains per process).
  - Kill switch = the presence of a file (`app/risk/kill_switch.py`); release is local CLI only.
  - Account verification after every (re)connect (`app/broker/verification.py`). Leverage is *not* identity,
    because FBS changes Forex leverage by equity tier.
- **Config:** secrets and safety flags come from env/`.env` (`EnvSettings`); parameters come from `config.yaml`
  (`AppConfig`, `extra="forbid"`). Env overrides yaml. Risk values are **percent** of equity with hard ceilings.
  `load_settings()` raises `ConfigError` on any problem.
- **Advisory (rev. 2):** "compute once, personalize per user". The engine computes market facts (evidence,
  opportunities, shadow trades); the cloud personalizer applies each user's theory selection, thresholds, windows
  and entitlements.
- **Web service (`app/web/`):** `create_app(WebSettings)`; settings are env only (`WEB_ENV` defaults to
  production). Protected routes take `CurrentSession`, mutations `CsrfSession`, control actions `StepUpSession`
  (`app/web/deps.py`). Expected errors are `ApiProblem(status, code, message)`. Users exist only via
  `app.cli web create-user`; TOTP is mandatory.
- **Frontend (`frontend/`):** Vite + React + TypeScript PWA, built into `frontend/dist` and served by FastAPI
  (same origin, strict CSP: no inline scripts, no CDNs, fonts bundled). Every API response is validated with zod.
  All UI text goes through react-i18next (`th` default, `en`); backend codes map to translation keys
  (`codes:<kind>.<CODE>`, `explain:<key>`). Parity tests read the backend enums and `app/advisory/explanations.py`,
  so **changing a reason code, status enum or explanation key/placeholder means updating
  `frontend/src/i18n/` in the same change** (run `npm run test` in `frontend/`).
- **Tests:**
  - `FakeMT5` (`app/broker/fake_mt5.py`) emulates the MT5 module, including server time, schedules per asset type,
    ticks, failures and call counters. Inject it via `MT5Client(..., mt5_module=fake)`.
  - Use `ManualClock` for time. Fixtures use Wednesday 2026-09-30 (market open, EEST +3) and Saturday 2026-10-03
    (market closed).

## Working rules

- Chat with the user in **Thai**. Docs, code comments and docstrings are in **English**. The PWA UI is Thai (default) +
  English, through translation keys only.
- After completing ticket items, tick them in `docs/TICKETS.md` via `scripts/tickets.py` in the same change.
- No Docker locally. `deploy/railway/*.Dockerfile` and `.railway/railway.ts` exist only for Railway builds.
- No profitability claims in any UI text either (`frontend/src/i18n/catalogs.test.ts` checks the catalogs).
- Ask before git commits, pushes, Railway deploys, or anything touching the user's accounts.
- LIVE trading stays disabled (no code path until Phase 14). DEMO orders need `TRADING_MODE=DEMO` plus
  `ENABLE_DEMO_TRADING=true` and a demo account. Subscription and billing stay behind `SUBSCRIPTIONS_ENABLED=false`.
