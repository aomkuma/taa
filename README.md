# TAA — FBS × MetaTrader 5 Automated Trading Platform

An automated Forex/CFD trading platform for an FBS account via MetaTrader 5, built around capital
protection: deterministic risk rules, circuit breakers, a kill switch, audit trails, backtesting,
paper trading, and a PWA dashboard.

> **No profitability claims.** The included strategy is a demonstration only. Leveraged FX/CFD
> trading carries a high risk of loss. Live trading is disabled by default.

## Documentation

- [docs/PLAN.md](docs/PLAN.md): architecture and design (research findings, risk model, breakers, sync, PWA).
- [docs/TICKETS.md](docs/TICKETS.md): tickets, checklists and progress.
- [docs/HANDOFF.md](docs/HANDOFF.md): current state and the prompt for resuming in a new session.
- [docs/CODING_STANDARDS.md](docs/CODING_STANDARDS.md): coding conventions (short version + commands in
  [CLAUDE.md](CLAUDE.md)).

## Topology (short)

- **Engine** runs natively on Windows next to the MT5 terminal. The `MetaTrader5` Python package is
  Windows-only.
- **Web (FastAPI + PWA), worker and PostgreSQL** run on Railway.
- The engine connects outbound over HTTPS only, and trading safety never depends on the cloud.

## Quick start (local, no Docker)

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt -r requirements/dev.txt
copy .env.example .env    # then fill in values; never commit .env
.venv\Scripts\python -m pytest
```

### Frontend (PWA)

Needs Node.js 22 or newer. See [frontend/README.md](frontend/README.md) for the stack and conventions.

```powershell
cd frontend
npm install
npm run dev     # http://127.0.0.1:5173; /api is proxied to the FastAPI service on 127.0.0.1:8000
npm run lint; npm run typecheck; npm run test; npm run build   # build output: frontend/dist
```

## Operator commands

```powershell
.venv\Scripts\python -m app.cli doctor            # read-only check of terminal, account, server time, symbols
.venv\Scripts\python -m app.cli doctor --fake     # same checks against the built-in FakeMT5
.venv\Scripts\python -m app.cli config show       # effective configuration (secrets masked)
.venv\Scripts\python -m app.cli kill --reason "..."            # activate the kill switch
.venv\Scripts\python -m app.cli kill --release --reason "..."  # release (local CLI only)
.venv\Scripts\python -m app.cli audit verify      # verify the tamper-evident audit chain
.venv\Scripts\python scripts\download_history.py --symbols EURUSD --timeframes M15,H1 --days 365
.venv\Scripts\python scripts\tickets.py show TAA-201  # ticket checklist helper
```

Databases: the engine keeps its authoritative state in `data/taa_engine.db` (SQLite). The web and
worker services use the PostgreSQL database `taa` on Railway, or `data/taa_cloud.db` locally.

More setup instructions (Windows host, MT5 terminal settings, Railway deployment) will be added as the
corresponding tickets are completed.
