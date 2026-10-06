# TAA — FBS × MetaTrader 5 Automated Trading Platform

An automated Forex/CFD trading platform for an FBS account via MetaTrader 5, built around capital
protection: deterministic risk rules, circuit breakers, a kill switch, audit trails, backtesting, paper
trading, advisory signals and a PWA dashboard.

> **No profitability claims.** The strategies are unproven; results in PAPER, DEMO, shadow trades and
> backtests describe the past and are no forecast. Leveraged FX/CFD trading carries a high risk of loss.
> LIVE (real money) is off by default.

## Documentation

- [docs/PLAN.md](docs/PLAN.md): architecture and design (risk model, breakers, sync, PWA, advisory, AI).
- [docs/TICKETS.md](docs/TICKETS.md): tickets, checklists and progress.
- [docs/HANDOFF.md](docs/HANDOFF.md): current state and the prompt for resuming in a new session.
- [docs/RUNBOOK_DEMO.md](docs/RUNBOOK_DEMO.md): broker orders on the demo account, the two-week soak.
- [docs/RUNBOOK_LIVE.md](docs/RUNBOOK_LIVE.md): the go-live checklist, drills, start/stop and back to safety.
- [docs/SECURITY_REVIEW.md](docs/SECURITY_REVIEW.md): the review before LIVE (threats, audits, secrets).
- [docs/CODING_STANDARDS.md](docs/CODING_STANDARDS.md): coding conventions (commands in [CLAUDE.md](CLAUDE.md)).
- [docs/STRATEGIES.md](docs/STRATEGIES.md), [docs/PATTERNS.md](docs/PATTERNS.md),
  [docs/INDICATORS.md](docs/INDICATORS.md), [docs/ADVISORY.md](docs/ADVISORY.md),
  [docs/COMPLIANCE.md](docs/COMPLIANCE.md).

## Topology (short)

- The **engine** runs natively on Windows next to the MT5 terminal; the `MetaTrader5` Python package is
  Windows-only. Its SQLite database is the authority for trading state.
- The **web** service (FastAPI + PWA), the **worker** and PostgreSQL are meant for Railway. The Railway
  deployment is deferred; locally they run on SQLite.
- The engine connects outbound over HTTPS only (HMAC-signed), and trading safety never depends on the cloud:
  the cloud can only lower risk, never raise it.

## Modes

| Mode | Orders | Needs |
|---|---|---|
| BACKTEST | simulated | `python -m app.cli backtest …` |
| PAPER | simulated book next to the real account | the investor password is enough |
| DEMO | real orders on a demo account | `ENABLE_DEMO_TRADING=true`, a DEMO account — [RUNBOOK_DEMO](docs/RUNBOOK_DEMO.md) |
| LIVE | real money | `ENABLE_LIVE_TRADING=true`, `LIVE_TRADING_CONFIRMATION=I-ACCEPT-LIVE-RISK-<login>`, a REAL account, the [go-live checklist](docs/RUNBOOK_LIVE.md) |

Risk: `config.yaml` → `risk` is the engine machine's cage; the owner's Trading profile in the PWA sets the
values used inside it, and its "Splitting an entry" plan decides how the bot enters (one order, several at
one price, or a market part plus resting limit parts) when `execution.entry_plans` is on. The optional AI review (`AI_PROVIDER=anthropic`) can only veto an entry; the optional AI
notes (`ai.advisory`) add a labelled opinion per opportunity and TH/EN narratives, and never change a score,
alert or trade (an opt-in alert filter acts only once the AI has measurably beaten the baseline).

## Quick start (local, no Docker)

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt -r requirements/dev.txt
copy .env.example .env    # then fill in values; never commit .env
.venv\Scripts\python -m pytest
scripts\start-demo.cmd    # web + worker + a FakeMT5 PAPER engine (once: scripts\start-demo.ps1 -Setup -Owner NAME)
scripts\start-demo.cmd -Mt5   # the same on the real MT5 terminal (PAPER), http://localhost:8001
scripts\start-demo.cmd -Mt5 -Demo   # real orders on the demo account (docs/RUNBOOK_DEMO.md)
```

FakeMT5 is pure Python and cannot reproduce every quirk of the real `MetaTrader5` module (on 2026-10-06 every
`order_check` on the real terminal failed while all tests passed). Before DEMO or LIVE, run the real-terminal
contract tests on the engine machine (a DEMO login; the trading part calls `order_check` only, never
`order_send`):

```powershell
$env:TAA_MT5_TESTS="1"; $env:TAA_MT5_TRADING_TESTS="1"; .venv\Scripts\python -m pytest -m mt5 tests/integration/test_mt5_terminal.py
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
.venv\Scripts\python -m app.main --mode paper|demo|live   # the engine; --mode must repeat TRADING_MODE
.venv\Scripts\python -m app.cli doctor            # read-only check of terminal, account, server time, symbols
.venv\Scripts\python -m app.cli config show       # effective configuration (secrets masked)
.venv\Scripts\python -m app.cli kill --reason "..."            # halt new entries (--mode FLATTEN closes)
.venv\Scripts\python -m app.cli kill --release --reason "..."  # release (local CLI only)
.venv\Scripts\python -m app.cli breaker list | breaker reset NAME --reason "..."
.venv\Scripts\python -m app.cli audit verify      # verify the tamper-evident audit chains
.venv\Scripts\python -m app.cli db backup         # online copy of the engine database, checked
.venv\Scripts\python -m app.cli db restore --from FILE --confirm FILE   # engine stopped
.venv\Scripts\python -m app.cli demo-report --days 14
.venv\Scripts\python -m app.cli strategy list   # strategies disabled remotely (re-enable is local only)
.venv\Scripts\python -m app.cli advisory rank | replay | calibrate   # advisory tools (never change trading)
.venv\Scripts\python -m app.cli ticks probe     # depth of market and tick history (read-only, disk-guarded)
.venv\Scripts\python -m app.cli sync upload-history [--send]   # local history to the cloud
.venv\Scripts\python -m app.cli web engine add --owner NAME --label X   # pair an engine (rotate | revoke | list)
.venv\Scripts\python -m app.cli web create-user NAME           # web users (TOTP mandatory)
.venv\Scripts\python -m app.cli engine new-totp   # the engine's control code (never sent to the cloud)
.venv\Scripts\python scripts\download_history.py --symbols EURUSD --timeframes M15,H1 --days 365
.venv\Scripts\python scripts\tickets.py show TAA-201  # ticket checklist helper
```

Databases: the engine keeps its authoritative state in `data/taa_engine.db` (SQLite; use a separate file for
LIVE). The web and worker services use PostgreSQL (`taa`) on Railway, or `data/taa_cloud.db` locally.
