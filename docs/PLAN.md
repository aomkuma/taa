# TAA — FBS × MetaTrader 5 Automated Trading Platform: Design

> Living design document (revision 2: advisory features, evidence engine, personalization; revision 3: Fibonacci
> extension levels and candle location, trading profile and entry plans, §A31). Work items and
> progress are tracked in [TICKETS.md](TICKETS.md). No profitability claims anywhere. Capital protection,
> fail-closed behavior and auditability take priority over features. Leveraged FX/CFD trading is high risk.

## Context

- **Request (rev. 1):** research what's needed and continue the design of the user's spec (sections 1–13, cut off
  mid-§13) for an automated FBS/MT5 trading platform, then implement it.
- **Request (rev. 2, 2026-10-03):** the user added three requirements:
  1. The system (or AI) analyzes account balance and leverage against every tradable symbol and outputs a **ranked list
     of symbols suitable to trade**.
  2. It monitors tradable symbols, the user's **favourites** and **user-defined lists**, and alerts when a setup's
     **% exceeds a user-set x%**, within suitable time windows. When a window passes, a badge shows
     "suitable time has passed".
  3. Even when the user doesn't trade an alert, the system records the **hypothetical outcome** of each recommendation:
     profit or loss per the plan, using the capital and lot size at that time. This history feeds **accuracy statistics**.
- **Status:** Phases 0–1 are DONE: foundation, config, secrets, logging, storage, audit, kill switch, CLI, CI, read-only
  MT5 gateway, FakeMT5, market data, `doctor`. 86 tests pass, and ruff/mypy/bandit are clean. Code lives in
  `C:\Users\korap\taa` (git initialized, nothing committed yet).
- **Rev. 2 decisions (user answers, 2026-10-03):**
  1. Show **both** a calibrated *win probability* and a *setup strength* score; the user chooses which one x applies to.
  2. A recommendation's window ends at the **earliest** of: signal lifetime, end of the market session, and the end of
     the user's own time windows.
  3. PWA and notifications are **Thai + English, switchable** (Thai default). Docs and code stay in English.
  4. The ranking scans **all asset classes**: Forex majors & minors, metals, indices, energies, crypto and single stocks.
  5. (follow-up) Each alert must explain **where its % comes from**, broken down by technical theory: Fibonacci
     retracement, price structures and chart patterns (triangles, M/W double tops/bottoms, ...), Elliott Wave, and every
     other feasible theory.
  6. (follow-up) **One alert can rest on several conditions at once** (confluence), which should raise confidence →
     §A29.
  7. (follow-up) Users can **switch theories and conditions on or off**, and the system computes **only the selected
     ones**. This needs settings pages, and the structure must be ready for a future **subscription package** → §A30.
- **Scope change (2026-10-03, after Phase 6):** the user chose to build Phase 12 (DEMO execution) before Phases
  6A–11. Broker orders are allowed on the **DEMO account only** (trade mode DEMO, `ENABLE_DEMO_TRADING=true`, the
  DEMO gate of §A3 passed). LIVE stays disabled until Phase 14 and an explicit go-ahead.
- **Workspace (rev. 1):** `C:\Users\korap\taa` was empty (greenfield).
- **Machine:** Windows 11 Home, Python 3.11.9, Node 24.18 / npm 11.16, Git 2.43 (Docker installed but not used locally).
  FBS MetaTrader 5 terminal at `C:\Program Files\FBS MetaTrader 5\terminal64.exe` (file version 5.0.0.6230). Terminal data
  shows servers **FBS-Demo** and **FBS-Real**; symbols seen: EURUSD, GBPUSD, USDJPY, USDCHF, XAUUSD, US30, UsDollar
  (no suffixes on this account; still detected at runtime, never assumed).
- **User decisions (2026-10-03):**
  1. Implement up to PAPER mode, then stop for review **before building broker order sending** → Milestone 1 = everything
     that never sends a broker order.
  2. Alerts/monitoring = a full **PWA**: dashboard, charts, symbols, positions & history, backtests, trade analytics
     (styles, brief reasons for each profit/loss), recommendations, and other necessary menus, with Web Push.
  3. All docs and code comments in **English**.
  4. Write the plan into the project as `.md` with **tickets + checklists** for progress tracking.
  5. **No Docker on localhost; deploy to Railway.**

---

## A1. Research findings that drive the design

| # | Finding | Design consequence |
|---|---|---|
| R1 | `MetaTrader5` on PyPI is 5.0.6231 (2026-09-27); wheels are **win_amd64 only** (CPython 3.6–3.14); it talks to a locally running terminal via IPC | The engine must run natively on Windows (PC or Windows VPS). Railway (Linux) hosts only web, worker and DB. Wine/`mt5linux` bridges are rejected for real money (fragile, unsupported). |
| R2 | `initialize()` auto-launches the terminal; without `login` it uses the **last account** and its saved password | Always pass explicit path/login/password/server. After connecting, verify `account_info().login/server/trade_mode` and `terminal_info()`; refuse on mismatch. Use a dedicated **portable** terminal copy for the bot. |
| R3 | Bar, tick and deal times come back as **broker-server wall-clock epochs**, not UTC (MQL5 forum, build 6182). History queries take UTC parameters per a moderator, but this is not officially documented | A `ServerClock` converts server time to UTC. History queries use windows widened by ±1 day and filter after conversion. |
| R4 | FBS MT5 server time is **EET**: GMT+2, and GMT+3 from the last Sunday of March 01:00 GMT until the last Sunday of October (EU DST) | Default `BROKER_TIMEZONE=Europe/Athens`, plus runtime offset verification from live ticks. Ship `tzdata`, because Windows has no IANA timezone database. |
| R5 | The Python API has **no** trading-session schedule and **no** economic-calendar functions | Session windows come from config, tick freshness and retcode 10018. A `NewsCalendar` interface ships with a manual blackout provider. |
| R6 | Market execution forbids `ORDER_FILLING_RETURN`; FOK/IOC are allowed according to the `symbol_info().filling_mode` flags (FOK=1, IOC=2) | A `FillingPolicyResolver` picks the mode per symbol and execution mode; nothing is hardcoded. |
| R7 | `order_check` success is retcode **0** ("Done"). `order_send` success is **10009** DONE or **10008** PLACED; 10010 is a partial fill. The full retcode table runs 10004–10046 | Explicit retcode handling matrix (§A12). |
| R8 | `order_send` can return **None** (request not sent, outcome unknown); details come from `last_error()` | Treat as UNKNOWN and reconcile before any retry. Never retry blindly. |
| R9 | Order comments are limited to **31 chars**, and brokers overwrite the tail (e.g. `[sl]`) | Identify orders by **magic number** plus a ticket mapping in the DB. Comments are ≤ 25 ASCII chars and informational only. |
| R10 | Logging in with the investor password gives read-only access (`trade_allowed=False`) | PAPER mode requires the investor password (least privilege) and uses a gateway that has no order methods. |
| R11 | Algo Trading button and options; `terminal_info().trade_allowed` and `tradeapi_disabled`; retcode 10027 when disabled | Preflight checks plus operator guidance in `doctor`. |
| R12 | The terminal's "Max bars in chart" setting caps `copy_rates_*` (`terminal_info().maxbars`) | Startup check against warm-up needs; history download in chunks. |
| R13 | `symbol_info` exposes digits, point, `trade_tick_size`, `trade_tick_value(_loss/_profit)`, `trade_contract_size`, `volume_min/max/step`, `trade_stops_level`, `trade_freeze_level`, `filling_mode`, `trade_mode`, `trade_exemode`, `chart_mode` and currencies. `order_calc_profit` and `order_calc_margin` return broker-computed P/L and margin in the account currency | Sizing uses `order_calc_profit` as the primary method with the tick-value formula as a cross-check. Any missing or inconsistent field means reject. |
| R14 | FBS supports EAs/algo trading on MT5. Third-party sources cite a 40% margin call and 20% stop-out, varying by entity and account | Read `margin_so_call/margin_so_so/margin_so_mode` at runtime and keep a far higher minimum margin-level guard. |
| R15 | Thread safety of the MT5 Python module is undocumented | All MT5 calls go through one gateway holding a lock (one session per process). |
| R16 | LINE Notify shut down on 2025-03-31 | The user chose the PWA with Web Push as the alert channel. |
| R17 | iOS Web Push works only for PWAs **added to the Home Screen** (iOS 16.4+), and permission must be requested from a user gesture. HTTPS, a service worker and a manifest are required | The PWA has an explicit "Enable notifications" button and install guidance; Railway provides HTTPS. |
| R18 | Railway runs Linux containers. Config-as-Code (`railway.toml/json`) is **deprecated and stops being read on 2026-12-01**; the replacement is IaC in `.railway/railway.ts` (`railway config plan/apply`). Private networking uses `*.railway.internal`; Postgres is exposed via a `DATABASE_URL` reference; regions include Singapore `asia-southeast1-eqsg3a`; `railway ssh` runs one-off commands. HTTP requests (including SSE) are capped at about 15 min, or 5 min idle | Use the IaC file, Dockerfile builds on Railway only, Postgres on the private network only, SSE heartbeats with client reconnect, and admin CLI tasks via `railway ssh`. |
| R19 | The original pandas-ta warns of discontinuation risk; TA-Lib has shipped official wheels since 0.6.5 | Indicators are implemented in-house (numpy/pandas, documented formulas). TA-Lib is only an optional reference in tests. |
| R20 | Lightweight Charts 5.x (Apache-2.0) requires TradingView attribution | Use it for price and equity charts and keep the attribution (logo option or NOTICE plus link). |
| R21 | Claude API: structured outputs via `output_config.format` or `client.messages.parse()` (Pydantic); `stop_reason == "refusal"` must be handled; server-side `fallbacks: "default"` (beta `server-side-fallback-2026-07-01`); the SDK defaults to a 10 min timeout and 2 retries; default model `claude-opus-5-5` ($4/$20 per MTok), with effort as the cost lever | AI layer (Milestone 2) is veto-only, uses a strict schema and a short timeout, turns a refusal into HOLD, enables fallbacks by default, and reads the model from `AI_MODEL`. |
| R22 | `symbols_get(group)` returns all symbols in one call; the filter supports `*` wildcards and `!` negation, comma-separated with inclusions before exclusions (e.g. `"*, !*EUR*"`) | The universe is discovered at runtime with configurable include/exclude patterns. Asset classes are inferred from `trade_calc_mode`, `path` and currency codes, never hardcoded. |
| R23 | `copy_ticks_range(symbol, from, to, COPY_TICKS_ALL)` returns tick history (`time_msc`, bid, ask) | Shadow trades resolve "SL and TP inside the same bar" exactly from ticks; only when ticks are unavailable do they fall back to a pessimistic rule (SL first). |
| R24 | FBS sets **Forex leverage by equity tier**: 1:3000 below $200, 1:2000 for $200–4,999, 1:1000 for $5k–29,999, 1:500 for $30k–149,999, lower above. Metals, indices, energies, crypto and stocks have **fixed instrument leverage** (e.g. metals 1:500, indices/energies 1:200, US30/US100/US500 1:500, stocks up to 1:100). The industry also commonly raises margin around news and weekends | Leverage is **not** an identity field: a leverage change is a WARNING that triggers margin re-checks, not ACCOUNT_CHANGE (fixes Phase-1 behavior, TAA-110). Margin is always computed with `order_calc_margin`, with a buffer factor for temporary margin hikes. |
| R25 | Badging API (`navigator.setAppBadge`) works for installed PWAs on iOS/iPadOS 16.4+ and on Windows/macOS (Chrome/Edge). Android Chromium shows a notification dot instead | The PWA sets the icon badge to the number of ACTIVE opportunities where supported; the in-app status badge is the source of truth. |
| R26 | Showing a notification with the same `tag` **replaces** the existing one; `renotify` controls whether the replacement alerts again; action-button support varies by platform | Each opportunity's push uses `tag = opportunity_id`. On expiry or invalidation a silent replacement says "suitable time has passed". No reliance on action buttons. |
| R27 | `Intl` locale `th-TH` defaults to the **Buddhist calendar** (2026 shows as 2569); `th-TH-u-ca-gregory` gives Gregorian years (verified with Node 24) | The Thai UI uses Gregorian dates for trading data (Buddhist era optional in settings). A self-hosted Thai font keeps the strict CSP. |
| R28 | For a driftless price, P(hit TP before SL) = SL/(SL+TP) = 1/(1+RR) (gambler's ruin). Including costs c (in R), the break-even win probability is (1+c)/(1+RR) | Every probability is shown next to its **random baseline** and **break-even** value so users can tell whether a setup beats chance. |
| R29 | Lo, Mamaysky & Wang (2000, *Journal of Finance*, "Foundations of Technical Analysis") define chart patterns (H&S, double/triple tops and bottoms, broadening, triangles, rectangles) algorithmically from sequences of local extrema of smoothed prices. They found several patterns carry **some incremental information**, not reliable predictions | Chart-pattern detectors use explicit extrema-based rules with tolerances, never discretionary drawing. Each detector's real value is **measured** on shadow/replay outcomes before it influences the %. |
| R30 | Harmonic patterns (Carney) are XABCD structures defined by Fibonacci ratios, e.g. Bat: AB 0.382–0.5 XA, BC 0.382–0.886 AB, CD 1.618–2.618 AB, D at 0.886 XA. Gartley, Butterfly and Crab use different ratio bands | Harmonic detectors are table-driven (ratio bands per pattern, configurable tolerance). Quality = ratio error; the completion zone (PRZ) is computed from the ratios. |
| R32 | Thailand: giving advice to the public on securities or **derivatives** for a fee is a licensed business (SEC). There are exemptions, e.g. advising ≤ 15 investors in 12 months without holding out as an advisor (Tilleke & Gibbins summary; SEC 2024 statement on foreign operators serving Thai investors). Thai PDPA also governs personal data | Subscription features ship **disabled** behind `SUBSCRIPTIONS_ENABLED=false` plus an owner-confirmed legal-review gate. `docs/COMPLIANCE.md` covers licensing questions for counsel and PDPA duties (notice, consent, retention, export/deletion). |
| R33 | Stripe is generally available in Thailand, including Stripe Billing for subscriptions; PromptPay works only for **one-time** payments, not recurring ones | A `BillingProvider` interface (Stripe as first candidate; recurring via card, PromptPay for prepaid periods) is designed but not implemented in Milestone 1. |
| R31 | Elliott Wave has three hard rules: wave 2 never retraces more than 100% of wave 1; wave 3 is never the shortest of 1/3/5; wave 4 does not overlap wave 1 (impulses). Automated counting is **inherently ambiguous** and recounts as new pivots confirm | Elliott counts are a **heuristic tier**: hard rules filter candidates, Fibonacci guidelines score them, primary + alternate counts are kept, and evidence is snapshotted at alert time so later recounts never rewrite history. |

## A2. Architecture

### A2.1 Deployment topology: hybrid, because MT5 is Windows-only

```
 Windows host (user PC or Windows VPS)                    Railway project (region: Singapore)
 ┌──────────────────────────────────────────┐            ┌───────────────────────────────────────────┐
 │ FBS MT5 terminal (dedicated, portable)   │            │ web  (FastAPI)                            │
 │      ⇅ IPC (MetaTrader5 package)         │  HTTPS     │  PWA static · REST · SSE · auth · push    │
 │ engine (Python)                          │ ─────────► │  /ingest (HMAC)  /engine/commands (pull)  │
 │  data · indicators · strategies · risk   │ outbound   ├───────────────────────────────────────────┤
 │  breakers · kill switch · paper/demo/live│ only       │ worker: backtests · analytics · watchdog  │
 │  position mgmt · local SQLite (authority)│ ◄───────── │         push dispatch · retention         │
 │  outbox sync · command poller            │ long-poll  ├───────────────────────────────────────────┤
 └──────────────────────────────────────────┘            │ postgres (private network only)           │
                                                          └───────────────────────────────────────────┘
 Phone / desktop ── HTTPS ──► web (installable PWA, Web Push via browser push services)
```

**Safety invariants of this topology**
1. Trading safety never depends on the cloud. If Railway or the internet is down, the engine keeps monitoring and enforcing
   breakers and the kill switch, the outbox buffers events, and the dashboard shows "last sync N min ago".
2. Every broker position carries a **broker-side SL**, so protection survives the engine dying.
3. The cloud detects engine silence (no heartbeat for 60 s during market hours) and sends a Web Push: **ENGINE OFFLINE**.
4. The cloud never holds MT5 credentials, AI keys or the control-TOTP secret. A full cloud compromise can at most activate
   the kill switch or disable strategies. Position closes require a TOTP code that the engine verifies itself.

**Local development** uses the same topology on localhost **without Docker**: engine + `web` (uvicorn) + `worker` + Vite
dev server, with the cloud DB as a local SQLite file. The production sync protocol is exercised locally.

### A2.2 Key decisions (deviations from the suggested structure, with reasons)

| ID | Decision | Reason |
|---|---|---|
| D1 | Hybrid: Windows engine plus Railway web/worker/Postgres | R1, R18; the user deploys to Railway |
| D2 | No local Docker and no docker-compose. Dockerfiles exist only for Railway builds (`deploy/railway/*.Dockerfile`), and Railway IaC replaces compose | User instruction; R18 |
| D3 | Ports & adapters: market-data/account gateway protocols; `MT5Gateway` (demo/live), `ReadOnlyMT5Gateway` (paper, with no order methods at all), `SimulatedBroker` (backtest and paper fills), `FakeMT5` module (tests) | Safety by construction, CI on Linux, parity between backtest, paper and live |
| D4 | The engine's local SQLite (WAL, `synchronous=FULL`) is authoritative for trading state: intents, breakers, HWM, processed candles, audit chain, outbox. Cloud Postgres is a replica plus the command queue | Trading must not depend on the network |
| D5 | Engine-to-cloud sync uses an idempotent event outbox and an HMAC-signed ingest API. Cloud-to-engine traffic is limited to expiring commands the engine pulls; dangerous commands need a TOTP code verified on the engine | Least privilege, no inbound ports, replay protection |
| D6 | One engine process with one MT5 session; MT5 calls are serialized. AI calls (M2) run in a worker thread with a deadline. The monitoring loop is never blocked | R15; spec: "AI failures must never stop monitoring" |
| D7 | Added packages: `core/`, `security/`, `engine/`, `backtest/`, `analytics/`, `sync/`, `web/`, `worker/`, `news/`, `cli/`, plus `frontend/`, `deploy/railway/`, `.railway/` | Homes for concerns the spec didn't place |
| D8 | Indicators are built in-house; TA-Lib is test-only | R19 |
| D9 | Fail-closed defaults everywhere: missing data, spec or acknowledgement means HOLD/reject; an unknown order state means halt and reconcile | Spec §12 |
| D10 | One SQLAlchemy model set plus Alembic (batch mode for SQLite), portable across SQLite and Postgres | One schema, two deployments |

### A2.3 Repository layout

```
taa/
├── app/
│   ├── main.py               # engine entrypoint: python -m app.main --mode paper
│   ├── config.py             # pydantic-settings: .env + config.yaml
│   ├── logging_config.py     # JSON logs + redaction
│   ├── core/                 # enums, value objects, Decimal helpers, ids (UUIDv7), errors, clock.py (Clock, ServerClock)
│   ├── security/             # secrets (env/keyring), redaction, live_gate.py, hmac_auth.py, totp.py
│   ├── broker/               # gateway.py (protocols), mt5_client.py, account_service.py, symbol_service.py,
│   │                         #   filling.py, retcodes.py, fake_mt5.py, execution_service.py (M2)
│   ├── market_data/          # candle_service.py, timeframe_service.py, quote_service.py, data_models.py, quality.py, history_store.py
│   ├── indicators/           # trend.py, momentum.py, volatility.py, volume.py, price_action.py
│   ├── strategy/             # base_strategy.py, example_strategy.py, signal_models.py, regime_detector.py,
│   │                         #   context_builder.py, registry.py, arbitration.py
│   ├── ai/                   # (M2) ai_provider.py, prompt_builder.py, response_parser.py, schemas.py
│   ├── risk/                 # risk_manager.py, position_sizer.py, exposure_manager.py, loss_tracker.py,
│   │                         #   circuit_breaker.py, kill_switch.py
│   ├── execution/            # order_manager.py, position_manager.py, trade_validator.py, simulated_broker.py
│   ├── engine/               # orchestrator.py, scheduler.py, decision_engine.py, reconciler.py
│   ├── backtest/             # engine.py, fill_model.py, costs.py, conversion.py, metrics.py, walk_forward.py, monte_carlo.py, report.py
│   ├── analytics/            # trade_builder.py, styles.py, attribution.py, recommendations.py, stats.py
│   ├── evidence/             # (rev. 2) framework.py (Evidence, registry, zigzag/pivots), fibonacci.py, levels.py,
│   │                         #   chart_patterns.py, candlesticks.py, momentum.py, volatility.py, ichimoku.py,
│   │                         #   structure_smc.py, harmonics.py, elliott.py, sessions_ranges.py, confluence.py
│   ├── advisory/             # (rev. 2) universe.py, asset_classes.py, market_sessions.py, suitability.py,
│   │                         #   preferences.py, confidence.py, calibration.py, scanner.py, lifecycle.py,
│   │                         #   shadow.py, replay.py, stats.py
│   ├── news/                 # calendar.py (interface + manual blackout windows)
│   ├── sync/                 # outbox.py, client.py, commands.py, history_upload.py
│   ├── monitoring/           # health_check.py, metrics.py, alerts.py (notification events), heartbeat.py
│   ├── storage/              # database.py, models.py, repositories.py, audit.py, migrations/ (Alembic)
│   ├── web/                  # FastAPI: api.py, auth.py, deps.py, routers/, sse.py, push.py, ingest.py, security_headers.py
│   ├── worker/               # job loop: backtests, analytics, engine watchdog, push retries, retention
│   └── cli/                  # python -m app.cli {doctor, kill, audit, backtest, web, sync, ...}
├── frontend/                 # React + TypeScript + Vite + vite-plugin-pwa
├── tests/                    # unit/, property/, integration/, backtest/, web/, fixtures/
├── scripts/                  # download_history.py, generate_vapid_keys.py, setup_windows_host.ps1, watchdog.ps1
├── deploy/railway/           # web.Dockerfile, worker.Dockerfile  (used only by Railway's builder)
├── .railway/railway.ts       # Railway IaC: web, worker, postgres
├── docs/                     # PLAN.md, TICKETS.md, INDICATORS.md, RUNBOOK.md, SECURITY.md, DEPLOY_RAILWAY.md, WINDOWS_HOST.md,
│                             #   (rev. 2) PATTERNS.md, ADVISORY.md, COMPLIANCE.md
├── data/  logs/              # gitignored (history parquet, taa_engine.db, taa_cloud.db, KILL_SWITCH, backups)
├── config.yaml  .env.example  .gitignore  pyproject.toml  README.md
├── requirements.txt          # aggregates requirements/base + engine + cloud (MetaTrader5 has a win32 marker)
└── requirements/             # base.txt, engine.txt, cloud.txt, dev.txt (pinned)
```

## A3. Trading modes

| | BACKTEST | PAPER | DEMO (M2) | LIVE (M2) |
|---|---|---|---|---|
| Market data | Parquet/Postgres history | live MT5 | live MT5 | live MT5 |
| Gateway | SimulatedBroker | ReadOnlyMT5Gateway + SimulatedBroker | MT5Gateway | MT5Gateway |
| MT5 password | none | **investor**; enforced via `trade_allowed == False` unless `PAPER_ALLOW_MASTER_PASSWORD=true` (warns) | master (demo) | master (real) |
| Required `account_info().trade_mode` | — | any | DEMO, otherwise refuse | REAL |
| Broker orders | never | never (no code path exists) | yes | yes, after the live gate passes |
| Extra gates | — | — | `ENABLE_DEMO_TRADING=true` | 6-condition live gate + probation |

The mode comes only from `TRADING_MODE` (required, no default) and is never inferred.
**Live gate (M2):** all of the following must be true:
- `TRADING_MODE=LIVE`
- `ENABLE_LIVE_TRADING=true`
- `LIVE_TRADING_CONFIRMATION == "I-ACCEPT-LIVE-RISK-<MT5_LOGIN>"` (the phrase is bound to the account)
- account, terminal and symbol validation passed: login, server, REAL, `trade_allowed`, `trade_expert`, terminal `trade_allowed`, `tradeapi_disabled` false
- risk config is valid
- the kill switch is inactive and no breaker is latched

LIVE start logs a prominent WARNING banner, and the first N live trades run at reduced risk (probation multiplier).

## A4. Configuration & secrets

- `.env` holds secrets and safety flags (including every env var the spec mandates). `config.yaml` holds non-secret
  parameters: symbols, timeframes, indicator params, strategies, risk details, sessions and per-symbol overrides.
  Precedence: env > yaml > code defaults. Pydantic models have range validators, unknown keys are rejected, and startup
  logs an effective-config summary with secrets masked.
- **Units:** risk values are **percent of equity** (`MAX_RISK_PER_TRADE=0.5` means 0.5%). Hard ceilings: 2% per trade,
  10% daily loss, 50% drawdown. Values above them stop startup. A unit mistake (0.01 meant as 1%) errs on the safe side.
- **Secret sources:** env/.env, or Windows Credential Manager via `keyring` (value `keyring:<service>/<name>`); Railway
  sealed variables in the cloud. `SecretStr` is used everywhere and secrets are never logged.

| Variable | Used by | Default | Notes |
|---|---|---|---|
| `TRADING_MODE` | engine | — (required) | BACKTEST / PAPER / DEMO / LIVE |
| `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER` | engine | — | password is a secret; PAPER uses the investor password; server e.g. `FBS-Demo` |
| `MT5_TERMINAL_PATH`, `MT5_PORTABLE`, `MT5_TIMEOUT_MS` | engine | —, true, 60000 | dedicated copy, e.g. `C:\MT5\taa-bot\terminal64.exe` |
| `BROKER_TIMEZONE` | engine | `Europe/Athens` | FBS EET/EEST, verified at runtime |
| `ALLOWED_SYMBOLS` | engine | `EURUSD,GBPUSD,USDJPY,XAUUSD` | validated against the broker |
| `MAX_RISK_PER_TRADE` | engine | 0.5 | % of equity |
| `MAX_DAILY_LOSS_PERCENT` | engine | 2.0 | broker-day basis |
| `MAX_ACCOUNT_DRAWDOWN_PERCENT` | engine | 10.0 | from the equity high-water mark |
| `MAX_OPEN_POSITIONS` | engine | 3 | |
| `MAX_SPREAD_POINTS` | engine | 30 | global fallback; per-symbol values in yaml |
| `ENABLE_DEMO_TRADING`, `ENABLE_LIVE_TRADING` | engine | false, false | |
| `LIVE_TRADING_CONFIRMATION` | engine | — | `I-ACCEPT-LIVE-RISK-<login>` |
| `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL`, `AI_MODE` | engine | none, —, `claude-opus-5-5`, veto | M2 |
| `KILL_SWITCH_FILE` | engine | `data/KILL_SWITCH` | |
| `ENGINE_DB_URL` | engine | `sqlite:///data/taa_engine.db` | local SQLite, authoritative trading state |
| `CLOUD_BASE_URL`, `ENGINE_ID`, `ENGINE_HMAC_SECRET` (+ `_PREVIOUS`) | engine, web | — | sync; sealed on Railway |
| `CONTROL_TOTP_SECRET` | **engine only** | — | verifies remote close/flatten codes |
| `DATABASE_URL` | web, worker | `sqlite:///data/taa_cloud.db` | Railway: Postgres database `taa` (reference variable) |
| `WEB_SESSION_SECRET`, `VAPID_PRIVATE_KEY`, `VAPID_PUBLIC_KEY`, `VAPID_SUBJECT` | web, worker | — | sealed on Railway |
| `WEB_IP_ALLOWLIST` | web | empty | optional |
| `LOG_LEVEL`, `LOG_DIR` | all | INFO, `logs` | |

## A5. Market data & time integrity

- **ServerClock:** `offset(t) = ZoneInfo(BROKER_TIMEZONE).utcoffset(t)`. To verify, sample `symbol_info_tick(ref).time_msc`
  twice about 10 s apart, and proceed only if ticks are advancing (market live): `raw = tick_time − now_utc`,
  `observed = round(raw/900)·900`.
  - `|raw − observed| > 120 s` means local clock drift and trips the CLOCK breaker.
  - `observed ≠ expected` trips the CLOCK breaker and sends an alert ("check BROKER_TIMEZONE / broker DST").

  Re-verify every 10 min and after weekends and DST dates. Historical server epochs are converted with tz rules; DST folds
  are handled and the ambiguous hour is documented.
- **Closed candles only:** `copy_rates_from_pos(sym, tf, 0, warmup+2)`, then keep bars where
  `open_server + tf ≤ server_now − grace`. The grace period defaults to 3 s and absorbs late ticks. Each bar stores both
  `time_utc` and `time_server`. Check that `chart_mode` is Bid (FX/CFD bars are Bid-based).
- **Dedup:** a per-(symbol, tf) watermark is persisted in `processed_candles`; evaluation fires exactly once per new closed
  entry-TF bar, including across restarts.
- **Quality checks:**
  - times are monotonic and unique
  - OHLC is consistent: `low ≤ min(o,c) ≤ max(o,c) ≤ high`, prices > 0, no NaN
  - gaps are detected session-aware (weekends and daily breaks are allowed)
  - stale data: tick age above `stale_tick_seconds` while the session is open, or the last closed bar is older than 2×tf
  - `maxbars` is sufficient

  A failure means HOLD with a reason; repeated failures trip the STALE_DATA breaker.
- **Multi-timeframe:** each TF is fetched independently. Higher TFs are joined by **close time** (`merge_asof` with
  `close_time ≤ decision_time`), so no look-ahead. Every MarketContext records the bar timestamps it used per TF.
  Supported TFs: M5, M15, M30, H1, H4, D1, plus optional M1 refinement; each can be enabled or disabled in yaml.
- **Reconnect:** exponential backoff (1→60 s), with account re-verification on every reconnect. The CONNECTION breaker
  blocks entries while disconnected.
- **Typed models:**
  - `SymbolSpec`, `Tick`, `CandleFrame`, `AccountSnapshot`, `TerminalSnapshot`
  - `MarketContext`: the spec §8 fields plus `atr`, `adx`, `spread_points`, `session`, `bar_times`, `quality_flags`

## A6. Indicators & features (pure functions, no I/O; `docs/INDICATORS.md`)

| Indicator | Definition and assumptions |
|---|---|
| SMA(n) / EMA(n) | arithmetic mean / α = 2/(n+1) seeded with SMA(n); NaN during warm-up |
| MACD(12,26,9) | EMA12 − EMA26; signal = EMA9 of MACD; histogram |
| RSI(14), ATR(14), ADX/±DI(14) | Wilder smoothing (α = 1/n); ATR uses True Range |
| Stochastic(14,3,3) | %K = (C − LL)/(HH − LL)·100, slowed; %D = SMA |
| CCI(20) | (TP − SMA(TP)) / (0.015 · mean absolute deviation) |
| Bollinger(20, 2) | SMA ± k·σ, with population σ (ddof = 0) |
| Historical volatility | stdev of log returns × √(bars per year for the TF) |
| Volume | tick volume (FX has no real volume): ratio to its SMA |
| Candle anatomy | body/range and upper/lower wick ratios |
| Swings | pivot high/low with k bars on each side, **confirmed only k bars later** (no look-ahead) |
| Structure | HH/HL/LH/LL from confirmed swings |
| S/R zones | confirmed swing prices clustered within ATR·tolerance; strength = number of touches |
| Breakout / false breakout | close beyond a zone + buffer (ATR fraction); false if it closes back inside within N bars |

All parameters are configurable. Insufficient data yields NaN, and the strategy returns HOLD (`INSUFFICIENT_DATA`).
A single indicator never produces a signal unless `allow_single_indicator_signals: true`.

## A7. Strategy engine & example strategy

- `BaseStrategy` provides `name`, `version`, `required_timeframes()`, `warmup_bars()` and
  `evaluate(ctx) -> Signal`. It is pure: no broker access, no credentials, no execution.
- `Signal` uses the spec §9 schema plus:
  - `signal_id`
  - `idempotency_key = sha256(strategy|symbol|tf|bar_close_utc|action)`
  - `data_timestamp_utc`, `strategy_version`
  - `expires_at_utc` (default: one entry bar)
  - `score`, a documented heuristic that is **not a probability**
- **Registry and arbitration:** strategies are loaded from yaml (enable/disable, params).
  - Cooldown of N bars per strategy and symbol; at most one signal per strategy, symbol and bar.
  - Opposite signals on the same symbol give HOLD (`CONFLICT`); for same-direction signals, the highest score wins.
  - An existing opposite position is never auto-reversed; only an explicit CLOSE closes it.
- **`example_trend_pullback`** (demonstration only, not production-proven, no profitability claim):
  - **H1 bias:** BULLISH when close > EMA200, EMA50 > EMA200 and ADX ≥ 20 (bearish mirrored); otherwise HOLD.
  - **Regime:** TRENDING (ADX ≥ 20), RANGING (ADX < 18), VOLATILE (ATR percentile > 90). Anything other than TRENDING means HOLD.
  - **M15 entry:**
    - price pulled back to EMA20 within the last 3 bars
    - then a bar closed back beyond EMA20 with RSI(14) crossing 50 in the bias direction
    - price is not within 1×ATR of an opposing S/R zone
  - **SL and TP:** SL goes beyond the last confirmed swing or 1.5×ATR, whichever is farther, plus a spread buffer; reject
    if it is more than 3×ATR away. TP = 2R; minimum RR 1.5.
  - **Filters:**
    - session window 07:00–20:00 UTC by default (per-symbol override)
    - spread ≤ the maximum and ≤ 15% of the SL distance
    - no new entries from Friday 20:00 UTC
    - 4-bar cooldown; at most 1 position per symbol
  - **Management:** move to break-even at +1R, trail at 2×ATR after +1.5R, and CLOSE if the H1 bias flips.

## A8. Decision engine & signal validation

The pipeline is deterministic. Every check is evaluated and persisted in `decision_checks` with its value and threshold.
Any failure means REJECT, with the exact reason codes:

| Group | Checks (reason codes) |
|---|---|
| System | KILL_SWITCH_ACTIVE, BREAKER_OPEN:&lt;name&gt;, BROKER_UNHEALTHY, STORAGE_UNHEALTHY, CLOCK_UNVERIFIED |
| Mode | ORDERS_NOT_ALLOWED_IN_MODE, LIVE_GATE_FAILED |
| Symbol | SYMBOL_NOT_ALLOWED, SYMBOL_UNAVAILABLE, SYMBOL_TRADE_DISABLED, DIRECTION_NOT_ALLOWED (LONGONLY/SHORTONLY/CLOSEONLY) |
| Data | DATA_STALE, DATA_GAPS, DATA_INVALID, SIGNAL_EXPIRED, PRICE_DRIFT (entry moved more than x·ATR) |
| Session | SESSION_CLOSED, MARKET_CLOSED, NEWS_BLACKOUT |
| Costs | SPREAD_TOO_HIGH, SPREAD_TO_SL_TOO_HIGH, EXPECTED_SLIPPAGE_TOO_HIGH |
| Signal | SL_MISSING, TP_MISSING, SL_WRONG_SIDE, SL_TOO_CLOSE (stops level + buffer), SL_TOO_FAR, RR_TOO_LOW |
| AI (M2) | AI_DISAGREES, AI_LOW_CONFIDENCE, AI_UNAVAILABLE; all mean HOLD in veto mode |
| Portfolio | MAX_OPEN_POSITIONS, MAX_POSITIONS_PER_SYMBOL, CONFLICTING_POSITION, DUPLICATE_SIGNAL, PENDING_INTENT_EXISTS, CORRELATION_LIMIT, CURRENCY_EXPOSURE_LIMIT, MAX_TOTAL_OPEN_RISK, UNKNOWN_POSITION_RISK (an open position without a stop), FOREIGN_POSITIONS (policy `halt`), COOLDOWN_ACTIVE |
| Account | DAILY_LOSS_LIMIT, WEEKLY_LOSS_LIMIT, MAX_DRAWDOWN, CONSECUTIVE_LOSSES, MARGIN_INSUFFICIENT, MARGIN_LEVEL_TOO_LOW, LEVERAGE_LIMIT |
| Sizing | SYMBOL_SPEC_INCONSISTENT, RISK_BELOW_MIN_LOT, VOLUME_INVALID |
| Broker precheck (M2) | ORDER_CHECK_FAILED:&lt;retcode&gt; |

The output is a `DecisionRecord`: decision, checks, volume, risk money, the bar times used per TF, config hash and code version.

(TAA-405) Each check is tagged HARD (the plan itself is invalid: data, geometry, RR, costs, closed market,
min lot or margin infeasible, symbol outside the universe) or ACCOUNT (limits, exposure, breakers, kill switch,
configured windows, news). The EXECUTION profile rejects on any failure; the ADVISORY profile rejects only on
HARD failures and shows failed ACCOUNT checks as warnings. A missing loss status fails the daily-loss check
(fail closed). The codes live in `app/risk/reasons.py`; `tests/unit/test_decision_engine.py` has one case per
Milestone 1 code.

## A9. Risk management & position sizing

**Sizing** (money in the account currency; Decimal for volume and price normalization):
1. `risk_budget = min(min(equity, balance) · risk% / 100, MAX_RISK_MONEY_PER_TRADE) × probation_multiplier`.
2. `entry` is a fresh ask for BUY or bid for SELL; SL is normalized to `trade_tick_size`.
3. `loss_1lot = −order_calc_profit(type, symbol, 1.0, entry, sl)`. It must be > 0; None means reject.
   `doctor` verifies the sign convention.
4. Cross-check: `ticks = |entry − sl| / tick_size` and `alt = ticks · trade_tick_value_loss`. If they differ by more
   than 10%, reject with `SYMBOL_SPEC_INCONSISTENT`.
5. `cost_1lot = commission_per_lot (yaml; FBS Standard = 0) + slippage_allowance_points · (point / tick_size) · tick_value_loss`.
6. `volume = floor_to_step(min(risk_budget / (loss_1lot + cost_1lot), volume_max, MAX_LOT), volume_step)`. Below
   `volume_min` means `RISK_BELOW_MIN_LOT`; volume is **never rounded up**.
7. Re-verify `volume · (loss_1lot + cost_1lot) ≤ risk_budget`.
8. Margin: `order_calc_margin` ≤ free margin × utilization cap, and the projected margin level must be
   ≥ `MIN_MARGIN_LEVEL` (default 500%, far above FBS stop-out). In M2, `order_check` must also return retcode 0.

**Exposure**
- Open risk = the sum of loss-to-SL across bot positions; capped by `MAX_TOTAL_OPEN_RISK`.
- Maximum positions per symbol.
- Correlation groups, e.g. `[EURUSD, GBPUSD]`: at most 1 in the same direction.
- Per-currency net direction count.
- Margin utilization = `margin / equity`.
- Effective leverage = `Σ |order_calc_profit(1% move)| × 100 / equity`. This is broker-computed and valid for FX, metals
  and indices.

**Loss accounting**
- Trading day and week boundaries follow broker time (EET; this matches FBS D1 bars). Start-of-day and start-of-week
  equity snapshots are persisted, and P/L includes floating P/L.
- External cash flows (deal types BALANCE/CREDIT) adjust the baselines, so deposits and withdrawals never trip or mask a limit.
- The HWM is persisted. Consecutive losses are counted from closed bot trades, net of costs.

**Defaults:**

| Limit | Default |
|---|---|
| Risk per trade | 0.5% |
| Daily loss | 2% |
| Weekly loss | 4% |
| Max drawdown | 10% |
| Consecutive losses | 4, then a 24 h pause |
| Max positions | 3 (1 per symbol) |
| Total open risk | 1.5% |
| Min RR | 1.5 |
| Max slippage | 10 points |
| Min margin level | 500% |
| Margin utilization | ≤ 30% |
| Effective leverage | ≤ 10× |
| Max lot | 1.0 (per-symbol override) |

**Stop-loss is mandatory, with no opt-out flag (fail-closed).** TP is required by default (`require_take_profit: true`).

## A10. Circuit breakers & emergency controls (continues spec §13)

**When a breaker trips:**
1. Stop opening new positions.
2. Keep monitoring and managing existing positions: SL enforcement, break-even/trailing, reconciliation.
3. Persist the breaker state with its reason, a metrics snapshot and timestamps, so it survives restarts.
4. Write an audit event and send a notification (Web Push for HIGH and CRITICAL).
5. Keep health checks and data feeds running.
6. Never auto-close positions, except in the explicit kill-switch FLATTEN mode or via the unprotected-position guard.
7. Reset only according to the policy below; every reset is audited with the operator and a reason.

| Breaker | Trigger (default) | Scope | Reset |
|---|---|---|---|
| CONNECTION | not initialized, `connected=false`, or `account_info` is None for > 15 s | global | auto after 3 healthy checks (half-open) |
| ACCOUNT_CHANGE | login/server/trade_mode/currency/leverage/margin_mode changed; unexplained balance change; unknown position with the bot's magic | global | manual |
| CLOCK | offset mismatch or local drift > 120 s | global | auto once verified |
| STORAGE | DB write/commit failure, or disk < 1 GB | global | auto after successful writes, with an alert |
| INVALID_PRICE | bid/ask ≤ 0, ask < bid, or a tick jump > 5×ATR | symbol | auto after 30 s of valid prices |
| SPREAD | spread > max for > 30 s, or > 3× the rolling median | symbol | auto after 60 s of normal spread |
| STALE_DATA | tick age > 120 s in session, or bars not updating | symbol | auto once fresh |
| SLIPPAGE | fill slippage > max, or 3 fills > 50% of max in a day | symbol | 60 min cooldown; manual if repeated |
| DAILY_LOSS / WEEKLY_LOSS | P/L ≤ −limit | global | next broker day / week |
| MAX_DRAWDOWN | drawdown from HWM ≥ limit | global | **manual only**, with acknowledgement |
| CONSECUTIVE_LOSSES | ≥ N | global / strategy | 24 h cooldown or manual |
| UNHANDLED_EXCEPTION | exception in the decision or execution path | global | 10 min cooldown; manual after 3 |
| ORDER_FAILURES (M2) | ≥ 3 failed sends in 15 min | global | 30 min cooldown; manual after 3 trips/day |
| DUPLICATE_EXECUTION (M2) | duplicate intent or an UNKNOWN order state | global | manual, after reconciliation |
| UNPROTECTED_POSITION (M2) | position without SL after 5 s and re-attach failed | global | manual (the guard closes the position) |
| SYMBOL_RESTRICTED (M2, added in Phase 12) | the server answered 10017/10018/10042–10044 (trade disabled, market closed, long/short/close only) | symbol | `execution.symbol_pause_minutes` cooldown |

AI failures never trip trading breakers; they only produce HOLD.

**Kill switch**
- **Activation:** the file `data/KILL_SWITCH`, checked every loop and immediately before any send; the CLI
  `python -m app.cli kill --reason "..."`; or a PWA command. A PWA activation needs no TOTP because it only reduces risk.
- **Modes:** HALT (default) blocks entries and keeps managing positions. FLATTEN closes all bot positions; it requires
  `KILL_SWITCH_FLATTEN_ALLOWED=true`, plus TOTP when triggered remotely.
- **Release:** **local CLI only** (`kill --release --reason`); never from the cloud.

## A11. Position management (paper in M1, broker in M2)

- **Every 1–2 s:**
  - verify an SL is present; if missing, re-attach it from the intent, otherwise close (M2)
  - break-even at +1R (SL moves to entry ± a cost buffer)
  - ATR trailing after +1.5R
  - optional time stop, CLOSE signals, and kill-switch FLATTEN
- **Invariants:**
  - the SL only moves in the favourable direction and is never removed
  - respect the stops level relative to the current price, and the freeze level
  - every change is at least a minimum step, with at most 1 modify per position per 10 s; retcode 10025 is ignored
- **Analytics:** track MAE/MFE per position from ticks.
- **Reconciliation:** compare broker and DB every cycle, matching bot positions by magic. Manual or foreign positions count
  toward exposure; the policy is configurable (count or halt).

## A12. Order execution & idempotency (Milestone 2, designed now)

- **Intent state machine:** NEW → PRECHECKED → SENDING → FILLED | PARTIAL | REJECTED | UNKNOWN → RECONCILED or
  NOT_EXECUTED. After FILLED: PROTECTED, or UNPROTECTED → EMERGENCY_CLOSED.
- **Write-ahead:** the intent row (unique `idempotency_key`) is committed before sending. Immediately before `order_send`,
  re-check the kill switch, breakers, connection, spread and price freshness (time-of-check vs time-of-use guard).
- **Request:**
  - `TRADE_ACTION_DEAL`, magic = `MAGIC_NUMBER_BASE + strategy_id`, comment `taa:<intent-short-id>`
  - filling mode from the resolver, `deviation` = max slippage points, `type_time` GTC
  - SL and TP included in the request

| Retcodes | Action |
|---|---|
| 10009, 10008 | Success: record the deal, order and position; check slippage; verify SL/TP |
| 10010 | Partial fill: record the actual volume and manage it as the filled position |
| 10004, 10020, 10021 | Requote or price changed: at most 1 retry with a fresh price if the signal is still valid; counts as a failure |
| 10012, 10031, `None` | UNKNOWN: reconcile (positions/orders/deals by magic + comment + time); no resend until resolved |
| 10013–10016, 10022, 10030, 10035, 10038 | Permanent request error: reject, alert, increment ORDER_FAILURES |
| 10017, 10018, 10042–10044 | Symbol trading restricted: pause the symbol |
| 10026, 10027 | Autotrading disabled on the server or terminal: global halt + operator alert |
| 10019 | No money: global halt |
| 10024 | Too many requests: back off and trip the breaker |
| 10033, 10034, 10040 | Broker limits: reject; review config |
| 10045, 10046 | FIFO or hedging prohibited: account-mode mismatch, halt |

- **Post-fill:** compare slippage with the requested price. If realized risk exceeds the planned risk by more than 20%,
  reduce or close per policy. If the SL is missing, re-attach it within 5 s, otherwise close and trip UNPROTECTED_POSITION.
- **Netting accounts** are refused until explicitly supported. FBS MT5 is expected to use hedging, verified at runtime.

## A13. Cloud sync (engine ↔ Railway)

- **Outbox** (engine SQLite):
  - every replicated record becomes an event `{event_id (UUIDv7), type, occurred_at_utc, payload}`
  - a sender thread sends batches of ≤ 500 events every 2 s, gzipped, with exponential backoff
  - priority order: audit, trades, decisions and breakers first, then snapshots, then quotes; quotes are coalesced when a backlog builds
  - it never blocks trading
- **Ingest:** `POST /api/v1/ingest/batch` with headers `X-Engine-Id`, `X-Timestamp`, `X-Nonce`, `X-Content-SHA256` and
  `X-Signature = HMAC-SHA256(secret, method|path|ts|nonce|body_sha256)`.
  - Reject requests with clock skew > 300 s or a reused nonce (10 min nonce store).
  - Payloads are schema-validated and upserted idempotently by `event_id`.
  - During rotation, the current and previous secret are both accepted.
- **Commands:** the engine long-polls `GET /api/v1/engine/commands?cursor=` (25 s). A command is
  `{id, type, params, created_by, created_at, expires_at (≤120 s), totp?}`.
  - The engine enforces an allowlist. KILL_SWITCH_ACTIVATE, STRATEGY_DISABLE and RESYNC need no TOTP.
  - POSITION_CLOSE and FLATTEN_ALL require a TOTP code verified on the engine against `CONTROL_TOTP_SECRET`, usable once.
  - **Risk-increasing commands are always rejected remotely:** release kill switch, reset breaker, enable strategy, change limits or mode.
  - Results are posted back and audited on both sides.
- **Heartbeats:** every 10 s. The worker raises ENGINE_OFFLINE after 60 s of silence during market hours (Web Push) and
  ENGINE_BACK when the engine resumes.
- **History:** `scripts/download_history.py` writes local Parquet and uploads closed candles to the cloud in chunks (for
  charts and cloud backtests). The engine also streams new closed candles continuously.

## A14. Web backend (FastAPI, Railway `web`)

- **Auth:**
  - single owner, with optional extra users
  - argon2id passwords; **TOTP mandatory** (pyotp)
  - server-side sessions: a hashed random token stored in the DB
  - cookie is `HttpOnly; Secure; SameSite=Strict`, with a 30 min idle and 12 h absolute timeout
  - CSRF header on mutations; login rate limit with exponential lockout
  - step-up TOTP for control actions; every login and command is audited
  - admin bootstrap only via `railway ssh -s web -- python -m app.cli web create-user`; there is no public setup endpoint
- **Security headers:**
  - strict CSP (`default-src 'self'`, no inline or eval, `frame-ancestors 'none'`)
  - HSTS, `nosniff`, `Referrer-Policy`, `Permissions-Policy`
  - no CORS (same origin only); all assets self-hosted; request size limits; optional IP allowlist
- **API `/api/v1`:**
  - status; account (snapshots, equity series)
  - symbols (spec, quote, context)
  - candles: indicator overlays computed server-side with the same `indicators` module, plus signal and trade markers
  - positions, intents, trades, signals, decisions (with checks); breakers and risk limits
  - control commands, notifications, push (VAPID key, subscribe, unsubscribe, test)
  - backtests (list, detail, compare, create job)
  - analytics (summary, styles, attribution, recommendations, per-trade explanation)
  - system (health, sync lag, clock, data quality, audit verification); config (effective, masked); auth
- **SSE `/api/v1/stream`:** topics are status, quotes, positions, notifications and decisions. A heartbeat comment goes out
  every 15 s, and clients reconnect with cursors (Railway caps a request at about 15 min).
- **Web Push:**
  - VAPID keys are generated with `scripts/generate_vapid_keys.py`; `pywebpush` sends from the worker
  - per-type preferences; dedup so the same type and symbol is sent at most once per 10 min (except CRITICAL)
  - minimal payloads: masked login, no balances
  - types: breaker trip/reset, kill switch, engine offline/back, paper/demo trade opened/closed, order failure (M2),
    unprotected position (M2), stale data or connection loss (debounced), daily summary, backtest finished
- **Worker:**
  - backtest jobs, one at a time with CPU and time limits
  - analytics recompute, engine watchdog, push retries
  - retention: quotes 7 days; snapshots 90 days, downsampled; trades and audit kept forever

## A15. PWA frontend

- **Stack:**
  - React + TypeScript + Vite + `vite-plugin-pwa` (Workbox)
  - TanStack Query, React Router, Tailwind CSS, and zod for API response validation
  - Lightweight Charts 5 for price, indicator, equity and drawdown charts (attribution kept), plus small SVG components for
    categorical analytics, using one accessible color system in light and dark
  - Built output is served by FastAPI; dev uses the Vite proxy to local FastAPI
- **PWA behavior:**
  - manifest: standalone, maskable and Apple icons
  - the service worker precaches the app shell
  - API GETs are network-first with a stale fallback and a "stale since" badge; mutations are never cached
  - push and notification clicks deep-link into the app; install prompt; iOS guidance to add to the Home Screen before enabling push
- **Pages:**

| Page | Content |
|---|---|
| Dashboard | mode banner (PAPER/DEMO/LIVE); engine, MT5, clock and sync health; equity and balance; daily/weekly P/L against limits (gauges); drawdown against limit; open risk; positions summary; breakers and kill switch; recent decisions and alerts |
| Charts | candles per symbol × TF; EMA and Bollinger overlays; RSI, ATR and ADX panes; S/R zones; signal and decision markers; trade entries and exits; SL/TP lines |
| Symbols | spec (digits, point, tick value, contract size, volume min/max/step, stops/freeze, filling, trade mode); live bid/ask/spread against limit; session state; context (HTF trend, regime, volatility); breaker state |
| Positions | open positions (R multiple, unrealized P/L, SL/TP, break-even/trailing state, MAE/MFE) and pending intents; close and flatten actions (TOTP) |
| History | closed trades with filters and CSV export; per-trade drawer with a timeline (signal → decision → fill → modifications → exit), reasons and a chart snapshot |
| Signals & Decisions | every signal with check-by-check results, filterable by reason code |
| Strategies | enabled state, parameters (read-only), per-strategy performance, disable action |
| Analytics | KPIs (net P/L, expectancy in R, win rate, profit factor, max DD, Sharpe/Sortino, average hold); equity and drawdown curves; R distribution; performance by style; MAE/MFE scatter; P/L attribution summary; scope selector (paper / demo / live / backtest run) |
| Recommendations | rule-based insights with evidence, sample size and confidence interval; a "Backtest this change" button; never auto-applied |
| Backtests | run list, run detail (metrics, equity/DD, trades, analytics), run comparison, walk-forward results, new run from presets |
| Risk & Controls | limits against current values, breakers and their history, kill-switch status and activation, control-command history |
| Notifications | notification center; push on/off per device; per-type preferences; test push |
| System | engine heartbeat, terminal and account info (masked), server-time offset, sync lag and outbox backlog, data quality, audit-chain verification, recent warnings |
| Settings | effective config (read-only, secrets masked); security (password, TOTP, sessions); about and attributions |
| AI (M2) | assessments, agreement rate, cost and budget |

- **UX:** mobile-first; dark and light themes; accessible; times shown in the user's timezone, with UTC and broker time on hover.

## A16. Trade analytics (`app/analytics`, deterministic)

- **Trade record:**
  - entry, exit, side, volume, initial SL/TP, initial risk (money and distance)
  - net P/L (including commission and swap), R multiple, holding time
  - exit reason: TP, SL, BE, TRAIL, TIME, SIGNAL, KILL_SWITCH, MANUAL, STOP_OUT
  - MAE/MFE in R; costs (spread, slippage, commission, swap)
  - entry context: HTF trend, regime, volatility percentile, session, ADX, spread/SL ratio, distance to S/R, news window
  - strategy and reason codes; AI assessment (M2)
  - (TAA-1001 decisions) `trade_builder.py` is pure; callers load the rows and pass them in.
    - Scopes: BACKTEST (`ClosedTrade`), PAPER (closed `paper_positions` plus their intents, which supply the
      initial stop and planned risk), SHADOW (CLOSED `shadow_trades` only, keeping `source` and `variant`).
      DEMO/LIVE are reserved for broker deals. Backtest, paper and shadow results are labelled hypothetical.
    - R is net of costs (`net / risk_money`; shadow: `r_net`); MAE/MFE in R use the fill-to-initial-stop
      distance. Outcome: |R| < 0.2 is a scratch.
    - Costs are money paid: commission and swap as recorded; spread from the decision quote (`ask - bid`) and
      slippage when the venue's per-fill slippage is fixed or recorded (market entries and every exit except
      TP and end of data), both valued at the trade's own money per price unit. Unknown components are None,
      so `cost_r` is then a lower bound.
    - Fills don't store the entry context: callers pass an `EntryContext` per signal id, built from the
      decision record (`context_from_decision`). Shadow rows supply session, entry-TF regime, ATR and HTF
      alignment from their stored features; "not aligned" is not treated as counter-trend.
    - A row that can't be turned into a faithful record is skipped with a reason, never guessed.
- **Style tags:**
  - setup (pullback or breakout, from reason codes), direction
  - holding style: scalp < 1 h, intraday < 24 h, swing ≥ 24 h
  - session (Asia, London, NY, overlap, off), regime, volatility bucket, weekday and hour, symbol
  - (TAA-1002 decisions) `styles.py`:
    - The setup comes from reason-code tokens (`PULLBACK`, `BREAKOUT`/`BREAK`), else from the strategy name
      (shadow rows store no reason codes), else OTHER.
    - The session comes from the entry context, else from `trading_session` at the entry instant. The regime
      is the entry timeframe's.
    - Volatility is the context's state, else ATR-percentile buckets (< 25 / < 75 / < 90 / else).
    - Weekday and hour are in UTC. Unknown facts are tagged UNKNOWN.
    - Every trade also carries strategy and scope tags; shadow trades add variant and source.
- **Attribution:** 1–3 reason codes per trade, each with a one-line text and its evidence values:

| Code | Rule / meaning |
|---|---|
| WIN_TRAILING_CAPTURE | a win (R ≥ 0.2) closed by the trailing stop |
| WIN_TREND_CONTINUATION | a win entered with the HTF trend |
| SCRATCH_BREAKEVEN | \|R\| < 0.2 (every scratch) |
| WEEKEND_GAP | a stop filled ≥ 0.25R beyond its level, after being held over a weekend |
| GAP_THROUGH_STOP | a stop filled ≥ 0.25R beyond its level (slippage included), no weekend |
| LOSS_IMMEDIATE_ADVERSE | MAE reached −1R within 3 bars and MFE < 0.3R |
| LOSS_GAVE_BACK_PROFIT | MFE ≥ 1R before the SL was hit |
| LOSS_REGIME_SHIFT | HTF trend flipped during the trade (to against the trade's side) |
| LOSS_VOLATILITY_SPIKE | entry-TF ATR at the exit ≥ 1.5 × at the entry |
| LOSS_NEWS_PROXIMITY | a news blackout window overlapped the trade |
| COUNTER_TREND_ENTRY | a loss entered against the HTF trend |
| COST_DOMINATED | costs > 30% of the absolute P/L before costs (in R) |
| HIGH_SLIPPAGE | slippage of the fills ≥ 0.1R |
| WIN_OTHER / LOSS_OTHER | fallback: no rule matched |

- (TAA-1003 decisions) `attribution.py`:
  - The rules run in the table's order and the first three that hold are kept; a trade with none gets the
    fallback code.
  - A rule whose facts are unknown doesn't fire: no initial stop, no exit-time trend or ATR, no news flag.
    Neutral or merely "not aligned" trends are never counter-trend.
  - Fills store no price path, so "−1R within 3 bars" means MAE ≥ 1R in a trade that lasted ≤ 3 entry-TF
    bars.
  - The HTF trend and ATR at the exit, and the news overlap, are optional context supplied by the caller.
  - Each code has an English one-line template rendered from its evidence values, plus a translation key
    `analytics.attribution.<CODE>` for the PWA. The attribution carries the trade's `hypothetical` label.
  - R thresholds compare with a 1e-9 tolerance, so a fill exactly at a level counts as reaching it.

- **Recommendations:** each one shows its evidence and a sample-size warning:
  - a segment with ≥ 30 trades whose bootstrap 95% CI of expectancy is entirely below 0 → "consider restricting"
  - more than 30% of losers had MFE ≥ 1R → "test an earlier break-even or partial TP"
  - more than 30% of SL hits were followed by price reaching TP within N bars → "SL may be tight relative to ATR"
  - cost drag above 25% → "review the spread filter or the symbol"
  - drawdown above 50% of the limit → "reduce risk"

  "Backtest this change" creates a parameter-variant backtest job. Recommendations **never** change live config.
  An optional AI narrative (M2) is clearly labelled as AI opinion.

## A17. Backtesting

- **Shared code:** the backtester uses the same strategy, decision, risk and position-management code;
  `SimulatedBroker` implements the gateway protocol.
- **Event loop:** iterates over entry-TF bar closes; higher TFs are aligned by close time. Decisions are made at the bar
  close and fill at the **next bar's open**: SELL at the bid open, BUY at open + spread (bars are Bid-based).
- **Costs and fills:**
  - spread from the bar `spread` field (indicative) or a configured fixed/percentile model
  - seeded slippage model
  - commission per lot per side; optional swap (snapshot of the symbol's swap rates, triple day per `swap_rollover3days`)
- **Intrabar SL/TP rules:**
  - BUY uses Bid lows and highs; SELL adds the spread
  - if SL and TP fall in the same bar, assume **SL first** (pessimistic)
  - a gap through the SL fills at the bar open
- **Currency conversion:** account-currency P/L uses conversion series (e.g. USDJPY, crosses); the symbol-spec snapshot is
  stored with the data.
- **Metrics:** net profit, CAGR, max equity DD, Calmar, Sharpe/Sortino (daily), profit factor, expectancy (money and R),
  win rate, average win/loss in R, trade count, exposure %, longest DD duration, cost breakdown, MAE/MFE.
- **Robustness:** walk-forward (rolling in-sample/out-of-sample windows), parameter sensitivity grid, Monte Carlo
  trade-order resampling (DD distribution), and explicit overfitting warnings.
- **Reproducibility and outputs:** every run stores its seed, config hash, data hash and code version. Outputs are a JSON
  summary, a trades CSV and an equity series, all rendered in the PWA.
- **Where it runs:** locally via the CLI (Parquet) or on the Railway worker (Postgres history); local runs can be uploaded.
- **Documented limitations:** bar-based approximation, spread model, no requotes or partial fills, news gaps.

## A18. Storage & audit

- **Engine SQLite:** runs, config_snapshots, processed_candles, market_contexts, signals, decisions, decision_checks,
  order_intents, paper_fills, trades, position_snapshots, account_snapshots, breaker_state, breaker_events,
  kill_switch_events, loss_baselines, notifications, outbox, audit_events.
- **Cloud Postgres:**
  - replicated read models: account snapshots, latest quotes, candles, contexts, signals, decisions with checks, positions,
    trades, breakers, notifications, audit events, heartbeats
  - cloud-only tables: users, sessions, push_subscriptions, control_commands, backtest_jobs/runs/trades/equity,
    analytics cache, ingest_nonces
- **Audit chain:** `audit_events` is append-only with `hash = sha256(prev_hash ‖ canonical_json(event))`, verified by
  `python -m app.cli audit verify`. The cloud also checks chain continuity on ingest; the result appears on the System page.
- **Backups:** the engine DB is copied nightly with `VACUUM INTO` to `data/backups` (14 kept). Railway Postgres uses the
  plan's backups, plus an optional `pg_dump` job.

## A19. Logging & monitoring

- **Logs:** JSON logs written with stdlib logging and a JSON formatter, rotating files (`logs/engine.log`, 10 × 20 MB),
  and a human-readable console. Correlation ids: `run_id`, `cycle_id`, `signal_id`, `intent_id`, `command_id`.
- **Redaction filter:** removes the exact value of every `SecretStr` and anything matching regexes (API keys, bearer
  tokens, `password=`); the MT5 login is shown only by its last 3 digits.
- **Metrics:** loop latency, MT5 call latency and errors, tick age and spread per symbol, open positions and risk, daily
  P/L %, drawdown %, breaker states, outbox backlog, sync lag, AI latency and cost (M2).
- **Engine-local health:** `http://127.0.0.1:8765/health` (localhost only) plus a heartbeat file. `scripts/watchdog.ps1`,
  run by Task Scheduler, restarts the engine if the heartbeat goes stale.

## A20. Security

| Threat | Controls |
|---|---|
| Credential leak | Secrets live only in env/.env, keyring or Railway sealed variables. `.env` is ACL-restricted to the bot user (icacls). `SecretStr` plus redaction. gitleaks in pre-commit and CI; `.gitignore`. Secrets never go to the AI or the cloud |
| Trading the wrong account | Explicit login/server, post-connect verification, DEMO mode refuses REAL accounts, the account-bound live phrase, a dedicated portable terminal |
| Runaway bot | Risk ceilings, breakers, kill switch (file, CLI and PWA), idempotency keys, rate limits, probation |
| Cloud compromise | The cloud holds no MT5 or AI secrets. The engine allowlists commands, requires an engine-verified TOTP for dangerous ones, and accepts only expiring single-use commands. No risk-increasing command is accepted remotely |
| Dashboard attack | argon2id + TOTP, lockout, secure cookies, CSRF, strict CSP, HSTS, no CORS, audit trail, optional IP allowlist, 2FA on Railway and GitHub |
| Ingest spoofing or replay | HMAC with timestamp, nonce and body hash; TLS; dual-secret rotation |
| Supply chain | Pinned dependencies and lockfiles, pip-audit, npm audit, bandit, ruff security rules, Dependabot |
| Tampering with history | Hash-chained audit trail, replicated off-host |
| AI misuse or prompt injection (M2) | Numeric inputs only, no account data, schema-validated output, veto-only, nothing is ever executed from text |
| Host compromise | Dedicated non-admin Windows user, no inbound ports, Defender, OS and terminal updates, 2FA on the FBS Personal Area, withdrawal restrictions |

**Credential rotation** (`docs/SECURITY.md`):

| Credential | Rotation steps |
|---|---|
| MT5 master or investor password | change it in the FBS Personal Area (or MT5 → Tools → Options → Server → Change), update keyring or `.env`, restart, verify |
| AI key | create a new key, update the config, revoke the old key |
| `ENGINE_HMAC_SECRET` | make the new secret primary and keep the old one as previous on Railway, update the engine, then remove the previous one |
| VAPID keys | rotate; clients re-subscribe |
| TOTP | re-enroll |
| Web passwords, Railway and GitHub tokens | change or reissue |

Cadence: every 90 days, or immediately on suspicion.
**Incident playbook:** activate the kill switch → rotate everything → review the audit trail and account history →
re-enable only via the local CLI.

## A21. Deployment & operations

- **Windows engine host:**
  - dedicated user; install FBS MT5 a second time into `C:\MT5\taa-bot\` and run it with `/portable`
  - log in once and enable Algo Trading
  - Tools → Options → Expert Advisors: allow algorithmic trading and make sure the Python API is not disabled
  - set "Max bars in chart" ≥ the requirement (or unlimited) and add the symbols to Market Watch
  - Windows time sync on; Python 3.11 venv
  - `python -m app.cli doctor` checks everything above
  - Task Scheduler task "at logon" plus the watchdog; on a VPS, disconnect the RDP session instead of logging off
  - a Windows VPS is recommended for DEMO/LIVE
- **Railway:**
  - one project in the Singapore region with services `web` and `worker` (Dockerfile builds from `deploy/railway/`) and `postgres`
  - `.railway/railway.ts` declares the services, variables (sealed for secrets), healthcheck `/api/v1/health`, pre-deploy
    `alembic upgrade head`, restart policy `ON_FAILURE` and watch paths
  - `web` gets a public HTTPS domain; `worker` and `postgres` stay private; app sleeping is off
  - deploy via the GitHub integration once CI passes, or with `railway up`; always run `railway config plan` before `apply`
  - **The first deploy, and any action touching your accounts, happens only with your go-ahead.**
- **Local dev (no Docker):**
  - `py -3.11 -m venv .venv`, `pip install -r requirements.txt -r requirements/dev.txt`, `npm ci` in `frontend/`
  - run `python -m app.web`, `python -m app.worker`, `npm run dev` and `python -m app.main --mode paper`

## A25. Advisory: symbol universe & suitability ranking (requirement 1)

**Goal:** rank every tradable symbol by how well it suits *this account right now*, given equity, balance, leverage and
risk settings. The output is a deterministic, explainable score. AI may add a narrative (M2) but never changes scores.
The ranking is **advisory only**: it never adds symbols to the bot's trading allowlist.

- **Universe (`universe.py`, `asset_classes.py`):**
  - Symbols are discovered with `symbols_get(group)` using include/exclude patterns (R22), refreshed daily, and
    persisted in `symbol_catalog`.
  - Asset classes come from `trade_calc_mode` + `path` + currency codes: FOREX_MAJOR / FOREX_MINOR / FOREX_EXOTIC /
    METAL / INDEX / ENERGY / CRYPTO / STOCK / OTHER. Every class is enabled by default except Forex exotics (opt-in);
    per-symbol overrides are allowed.
  - Monitored set = favourites ∪ custom lists ∪ AUTO top-N (default 30) ∪ `ALLOWED_SYMBOLS`, capped at 60 so
    terminal load stays bounded.
- **Market sessions (`market_sessions.py`):**
  - Sessions are defined in **exchange-local timezones**, so DST is handled by zoneinfo:
    - Sydney 07–16 Australia/Sydney
    - Tokyo 09–18 Asia/Tokyo
    - London 08–17 Europe/London
    - New York 08–17 America/New_York
    - US equities and indices: cash session 09:30–16:00 America/New_York, plus the broker's extended hours
    - crypto 24/7
  - Each asset class maps to sessions; per-symbol overrides are allowed.
  - A **liquidity profile** (median tick volume per hour-of-week, from H1 history) tells whether a symbol is active
    "now" on this broker.
- **Inputs per symbol:**
  - account snapshot: equity, balance, free margin, leverage tier
  - risk settings and `SymbolSpec`
  - ATR (H1, D1) and ATR percentile
  - median and current spread
  - session state and liquidity
  - open exposure and rolling H1 return correlations
  - historical edge, i.e. posterior expectancy from shadow/replay outcomes (§A27)
- **Hard gates.** Failing any gate means *not suitable*, with an explanation. `typical_SL = k × ATR(entry TF)` +
  spread, where k comes from the strategy (default 1.5).

  | Gate | Rule | Explanation shown to the user |
  |---|---|---|
  | G1 Tradable | trade_mode allows a direction, the spec is valid, and a filling mode exists | which condition failed |
  | G2 Min-lot affordability | `volume_min × loss_per_lot(typical_SL) ≤ risk_budget` | "minimum lot risks $X vs your budget $Y; needs equity ≥ $Z" |
  | G3 Margin | margin of the risk-sized lot × buffer (default 2×, R24) ≤ free margin × utilization cap; projected margin level ≥ minimum | margin needed vs available |
  | G4 Cost | (median spread + commission) / typical_SL ≤ `max_spread_to_sl_ratio` | cost share of the stop |
  | G5 Stops level | `stops_level × point` < 0.5 × typical_SL | broker stop distance vs typical stop |
  | G6 Data | fresh quotes (checked only while the symbol's market is open) and enough candles | which data is missing or stale |

- **Soft scores (0–100, configurable weights):**

  | Score | Measures | Higher is better when |
  |---|---|---|
  | S1 Sizing granularity | `log2(risk_budget / min_lot_risk)` scaled 1×→0 … 16×→100 | there is more headroom above the minimum lot |
  | S2 Cost efficiency | cost / typical_SL | costs are a smaller share of the stop |
  | S3 Leverage/margin comfort | effective leverage = Σ\|calc_profit(1% move)\|×100 / equity, and margin share | both are lower |
  | S4 Liquidity now | current hour-of-week tick volume vs the symbol's median | the symbol is more active now |
  | S5 Volatility regime | ATR percentile; the 20–80 band is best | volatility is moderate |
  | S6 Regime fit | match with the enabled strategies' preferred regime (e.g. trend → ADX) | the regime fits |
  | S7 Diversification | correlation to open exposure and to higher-ranked picks (penalty) | correlation is lower |
  | S8 Historical edge | shrunk posterior expectancy in R; neutral 50 with an "insufficient data" flag when there's too little history | expectancy is higher |
  | S9 Holding cost | swap per day vs typical_SL (swing holds) | swap costs less |

- **Outputs:**
  - **Overall** score (structural: S1, S2, S3, S8, S9) and **Now** score (adds S4–S7). The list is sorted by Now
    score, eligible symbols first and, within them, symbols whose market is open now first.
  - Each row also carries:
    - suggested lot and risk money at typical_SL; min-lot risk and required equity
    - margin, effective leverage, cost %, session state, best hours (UTC)
    - gate results and explanation keys (TH/EN)
- **Scheduling:**
  - structural refresh every 6 h and whenever equity changes by ±5%
  - dynamic metrics hourly, in round-robin batches of about 20 symbols per minute
  - Now score each minute from cached metrics
  - an on-demand RESCAN command
- **Persistence:** results go to `suitability_snapshots` (latest per symbol plus hourly history, 90-day retention) and
  replicate to the cloud.

## A26. Advisory: watchlists, opportunities & alert windows (requirement 2)

- **Preferences (`preferences.py`, shared models):** per user and authoritative in the cloud (edited in the PWA).
  The engine never needs per-user preferences: it receives only the **compute requirements** derived from them
  (§A30), cached with version/ETag. `config.yaml` → `advisory:` provides a fallback when no cloud is configured.
  - Watchlists: FAVOURITES, CUSTOM (named), AUTO_TOP_N (from the ranking). Each list has an alerts on/off switch and
    an optional threshold override.
  - **Alert metric:** WIN_PROBABILITY or SETUP_STRENGTH (user choice). Global threshold **x**, overridable per list
    (defaults: 55% for win probability, 75% for setup strength).
  - Window rules: signal lifetime in bars (default 2 entry bars); market session (on/off); user time windows in the
    user's timezone (Asia/Bangkok by default).
  - Rate limits (max alerts/hour, cooldown per symbol); expiry-update push (on/off); language (TH/EN).
- **Two numbers on every opportunity (`confidence.py`):**
  - **Setup strength (0–100):** weighted share of the strategy's condition checklist that passed (deterministic,
    available immediately).
  - **Win probability:** calibrated P(TP before SL).
    - Computed as a hierarchical Beta-binomial posterior over *strategy × symbol × strength bucket × RR band*, pooled
      toward *asset class → strategy* (empirical Bayes, pseudo-count κ≈20).
    - Shown with its 90% credible interval and sample size *n*; below the minimum *n* it shows "insufficient data".
    - Shown next to the **random baseline** 1/(1+RR) and the **break-even** (1+c)/(1+RR) (R28), plus expected value
      `EV(R) = p(RR+1) − 1 − c`.
  - Historical replay (§A27) provides the initial calibration from day one, labelled "backtest-calibrated" until
    live shadow outcomes accumulate.
- **Scanner (`scanner.py`):** on every new closed entry-TF bar, for each monitored symbol:
  1. Build the context and evaluate the enabled strategies.
  2. Run the decision engine in its **ADVISORY profile**:
     - Hard failures hide the alert: invalid data, closed market, bad SL/TP geometry, RR below minimum, spread over
       limit, min-lot or margin infeasible.
     - Account-rule hits become **warnings** on the card (e.g. "daily loss limit reached").
  3. Size the lot and compute risk and reward money from the **current equity**.
  4. Create a **market Opportunity** record (idempotent per strategy/symbol/bar/side) for *every* candidate that
     passes the hard checks, alerted or not, carrying its full evidence and model features. Hard failures keep
     their reasons in `decision_records` (profile ADVISORY) and get no opportunity and no shadow trade.
  5. **Alert decisions are per user and happen in the personalizer (§A30), not in the engine.** A user is alerted
     when **metric ≥ x** with that user's enabled theories, minimum supporting theories are met, the user's windows
     are open, the symbol session is open, the list has alerts on, the rate limit allows, and it isn't a duplicate.

  Scanner work is time-boxed per loop cycle, so position monitoring and breakers keep priority.
- **Window (`lifecycle.py`):**
  - `valid_until` = **earliest** of:
    - signal lifetime end (bar close + N bars)
    - end of the symbol's current market session
    - end of the user's current time window
    - start of the next news blackout
  - The reason is stored, e.g. "London session ended".
  - **Early invalidation:** price drifts more than 0.5×ATR beyond the entry, price touches the SL before entry, the
    spread stays over its limit for more than 30 s, or an opposite signal appears.
  - **Statuses:**

    | Status | Meaning |
    |---|---|
    | CANDIDATE | below threshold, tracked silently |
    | ACTIVE | alerted and inside its window |
    | EXPIRING | UI-derived: less than 20% of the window remains |
    | EXPIRED | window passed: badge "หมดเวลาที่เหมาะสมแล้ว / suitable time has passed" plus the reason |
    | INVALIDATED | conditions broke; the reason is shown |
    | FOLLOWED | a manual position on the same symbol and side (magic 0) opened inside the window, detected read-only from account positions |

  - Restart catch-up expires windows that passed while the engine was down.
- **Notifications** (sent by the personalizer, §A30):
  - Localized TH/EN by user language; `tag = opportunity_id`.
  - Body: symbol, side, both metrics, entry/SL/TP, lot and risk money, "valid until HH:MM (Thai time)".
  - On expiry or invalidation, a silent same-tag replacement is sent if enabled (R26).
  - The payload carries the active-opportunity count for the app icon badge (R25). An in-app notification center
    keeps the history.

## A27. Advisory: shadow trades, accuracy & calibration (requirement 3)

- **Shadow trades (`shadow.py`):** every opportunity, alerted or not (needed for unbiased calibration), gets
  hypothetical trades:
  - **Entry:** at signal time at the actual ask (BUY) or bid (SELL), with the recorded spread and the configured
    slippage.
  - **Sizing:** lot and `equity_at_signal` snapshotted using the PositionSizer at that moment. If sizing fails, the
    trade is tracked in R only, flagged "not tradable at your capital".
  - **Variants:** **PLAN** (fixed SL/TP, the primary "as planned" result) and **MANAGED** (break-even/trailing per
    `position_management`).
  - **Resolution:** M1 bars; when one bar contains both SL and TP, ticks via `copy_ticks_range` (R23) decide, else
    SL-first with an AMBIGUOUS flag. Also time stop (default 72 h) and gap-through-stop fills at the bar open.
  - **Costs and result:** commission and a swap estimate; P/L in account currency via `order_calc_profit` with the
    snapshotted lot; R multiple; MAE/MFE.
  - **Durability:** persisted and caught up after restarts from M1 history. Results are hypothetical and labelled
    so: no requotes, partial fills or real slippage.
  - (TAA-6C1 decisions) Implemented in `shadow.py` (pure, shared with replay) and `shadow_tracker.py` (engine):
    - The entry uses the quote the ADVISORY decision used; opportunities now store `bid`, `ask`, `quote_at`.
    - The M1 bar holding the entry instant is resolved from its ticks after the entry; without ticks only a
      stop touch counts (`PARTIAL_BAR`), because its range includes prices from before the entry.
    - An open beyond the TP fills at the TP (never better). MANAGED applies the A11 rules at every M1 close,
      with the ATR recorded at signal time.
    - A fill already at or beyond the stop makes the trade `VOID` (excluded from statistics).
    - Shadow rows copy the signal facts (strength, RR, features, session, ATR), so outcomes stand alone and
      replay trades need no opportunity row. `alerted` comes from the opportunity's `alerted_at` (set by
      `mark_active`, kept after expiry), `followed` from status FOLLOWED.
    - Commission: `advisory.shadow.commission_per_lot` unless the symbol override sets one. Swap: the
      per-lot nightly swap (S9's conversion) × rollover days; unknown swap modes are flagged `SWAP_UNKNOWN`.
- **Historical replay (`replay.py`):** replays the scanner over N months of history per symbol, reusing the backtest
  components (resolution on M5/M1). Outcomes are tagged `source=REPLAY` and bootstrap calibration. Runs via the
  local CLI or a cloud worker job.
- **Calibration (`calibration.py`):**
  - Rebuilt nightly and on demand into versioned bucket tables.
  - REPLAY outcomes act as a capped prior (≤ 50 pseudo-counts) and LIVE outcomes update it.
  - Also produces the Brier score and reliability data.
  - Every opportunity stores the `calibration_version` it used.
- **Accuracy statistics (`stats.py`, shared with cloud analytics):**
  - Core metrics:
    - hit rate (TP-first ÷ resolved) with Wilson CI
    - expectancy (R and money) and profit factor
    - **total hypothetical P/L at the lot sizes of each moment**
    - a "follow every alert ≥ x" equity curve with max drawdown
  - Calibration: predicted vs observed, per bucket.
  - Breakdowns: symbol, strategy, asset class, session, bucket, watchlist, alerted vs not, followed vs not, AI
    agree/disagree (M2).
  - **Threshold explorer:** sweeps x and is marked in-sample.
  - Live and replay results are always reported separately.
- **Feedback loops:** accuracy feeds S8 (historical edge) in the ranking and the win-probability estimate. Shadow
  trades also enter `app/analytics` as scope SHADOW, so styles and P/L attribution work for them too.

## A28. Localization & advisory UI

- **Localization:** react-i18next with `th` (default) and `en`.
  - Dates via `th-TH-u-ca-gregory` (R27), with Asia/Bangkok as the default display timezone.
  - Self-hosted Noto Sans Thai.
  - Server-side TH/EN templates for push.
  - Explanation and reason codes map to translation keys.
- **New pages:**

  | Page | Content |
  |---|---|
  | Symbol Ranking (จัดอันดับสินทรัพย์) | account header (equity, balance, leverage tier, risk %); sortable Now/Overall table; filter by asset class; gate chips; "needs equity ≥ $Z" hints; ★ adds to favourites; detail drawer with every score |
  | Opportunities (โอกาสเข้าเทรด) | live cards with both metrics + baseline/break-even + EV, lot/risk/reward money, entry/SL/TP, countdown, status badge with reason, chart link |
  | Watchlists (รายการโปรด) | favourites and custom lists; per-list alerts and x override; auto top-N |
  | Alert settings (in Notifications) | metric choice, x slider, user time windows, session rule, rate limits, expiry updates, language |
  | Signal Accuracy (ความแม่นยำ) | KPIs; follow-all equity curve; calibration chart; strength buckets vs hit rate; breakdowns; outcome history with hypothetical P/L; live/replay toggle; threshold explorer |
  | Dashboard additions | top-5 ranked symbols, active opportunities, accuracy summary |

- **Engine ↔ cloud:**
  - New event types: `symbol_catalog`, `suitability_snapshot`, `opportunity` (create/update), `shadow_trade`
    (create/update/resolve), `calibration_version`.
  - `GET /api/v1/engine/advisory-config` (HMAC, ETag) delivers **compute requirements** (§A30): the monitored-symbol
    union, the detector/strategy union, and window/lifetime parameters. Per-user preferences stay in the cloud.
  - New command RESCAN_SUITABILITY (no TOTP). Watchlist and threshold changes affect **alerts only**, never the
    bot's trading universe or risk.
- **Storage:**
  - Engine tables: `symbol_catalog`, `suitability_snapshots`, `opportunities`, `shadow_trades`,
    `calibration_tables`, `advisory_preferences_cache`.
  - Cloud adds `watchlists`, `watchlist_symbols`, `alert_preferences`, and `users.locale` / `users.timezone`.
- **Docs:** `docs/ADVISORY.md` covers formulas, definitions, baselines, shadow assumptions and caveats.

## A29. Technical evidence engine & explainable confluence probability (rev. 2 follow-ups 5–6)

**Goal:** every opportunity lists *all* the technical theories that support or contradict it, and states how much each
one moves the %. Multiple agreeing conditions raise confidence, but correlated conditions are never double-counted.
Whether a theory actually helps is **measured** on shadow/replay outcomes (R29), not assumed.

- **Framework (`evidence/framework.py`):**
  - Detectors are plugins in a registry, each enabled/disabled with parameters from `config.yaml` → `evidence:`.
  - Each detector returns `Evidence` records with these fields:

    | Field | Content |
    |---|---|
    | detector_id, family, name | which theory fired |
    | direction | BULL / BEAR / NEUTRAL |
    | timeframe, detected_at | confirmation bar |
    | quality | 0–1 geometric/ratio fit |
    | key_levels | neckline, fib levels, pattern points... |
    | invalidation, targets | where it fails / measured-move targets |
    | age_bars, objectivity tier | T1 objective, T2 rule-based geometric, T3 heuristic |
    | i18n key | TH/EN label |

  - A shared multi-degree **zigzag/pivot engine** (ATR-scaled thresholds, confirmation lag) feeds every swing-based
    detector.
  - **No look-ahead:** evidence at bar T uses only bars ≤ T and confirmed pivots. Each opportunity stores an immutable
    evidence snapshot, so later redraws or recounts never rewrite history.
- **Initial detector catalog** (≈60 detectors; extensible; one opportunity can carry many):

  | Family | Detectors | Tier |
  |---|---|---|
  | Fibonacci | retracements 23.6/38.2/50/61.8/78.6 of the last impulse · "golden zone" pullback + rejection · extensions 127.2/161.8 (targets) · (rev. 3) extension levels 127.2/161.8/261.8/423.6 as support/resistance, two-point and trend-based (A-B-C) · fib cluster confluence | T1 |
  | Levels | S/R zones (TAA-205) · round numbers · classic/Fibonacci/Camarilla pivots · previous day/week high/low | T1 |
  | Trend & structure | Dow structure HH/HL/LH/LL · break of structure (BOS) / change of character (CHoCH) · trendlines and channels from pivots · MA alignment/crosses, price vs EMA200 · ADX trend strength | T1 |
  | Chart patterns | double top **M** / double bottom **W** · triple top/bottom · head & shoulders (+inverse) · triangles (ascending/descending/symmetrical) · wedges (rising/falling) · rectangles · flags/pennants · cup & handle; neckline/boundary break confirmation, measured-move targets | T2 |
  | Candlesticks | engulfing · hammer/pin bar · shooting star · doji family · inside/outside bar · morning/evening star · three soldiers/crows · harami · tweezer · marubozu; weighted by location (at S/R/fib) | T1 |
  | Momentum | RSI/MACD/Stochastic **regular & hidden divergences** (pivot-based) · overbought/oversold · MACD/Stochastic crosses · CCI extremes | T1 |
  | Volatility & volume | Bollinger squeeze → breakout · Keltner · Donchian breakout · ATR expansion · tick-volume spike/climax · session VWAP (tick volume) | T1 |
  | Ichimoku | price vs cloud · Tenkan/Kijun cross · Kumo breakout · Chikou confirmation (9/26/52) | T1 |
  | Smart-money / Wyckoff | liquidity sweep (stop hunt) · fair value gap · order block · supply/demand zone · Wyckoff spring/upthrust | T2 |
  | Harmonics | Gartley · Bat · Butterfly · Crab · Cypher · Shark · AB=CD (ratio tables, PRZ, completion) | T2 |
  | Elliott Wave | impulse/correction candidates with the 3 hard rules + Fibonacci guideline scoring; primary + alternate counts; "possible wave 3 / wave 5 / C completion" states | T3 |
  | Sessions & time | Asian-range breakout · London/NY open breakout · hour-of-week seasonality | T1 |

  Backlog: Gann and Market Profile (low objectivity, or needs volume the MT5 retail feed lacks).
- **(rev. 3) Location of single-bar evidence.** Candlestick quality is weighted by location: a pattern whose bars
  coincide with a same-direction rejection from a level source scores higher. The sources are Fibonacci
  retracement and extension levels, Fibonacci clusters, S/R zones, round numbers, pivots, previous day/week
  high/low, and trendline bounces. The record names the levels it sat on (`at_levels`), so an explanation can
  say "shooting star at the Fibonacci 161.8 % resistance". Combining independent theories into one score
  remains the job of the confluence score (TAA-307) and the evidence model (TAA-6B2).
- **Two uses of evidence:**
  1. **Confluence enrichment for every opportunity.** All active evidence on all enabled timeframes (including HTF)
     is attached to every opportunity and classified as *supports* or *conflicts* relative to the trade direction.
  2. **Pattern-based strategies (setup generators).** Tradable detectors produce their own opportunities with explicit
     entry/SL/TP rules, all labelled demo/unproven and each enable/disable:

     | Setup | Entry | SL / TP |
     |---|---|---|
     | M/W and H&S | neckline-break close | beyond the pattern extreme / measured move |
     | Triangle, wedge, rectangle, flag | boundary break | pattern height |
     | Fibonacci pullback continuation | golden-zone rejection | beyond 78.6% / prior high or 127.2% |
     | Harmonic PRZ reversal | reversal at the PRZ | beyond X or the PRZ / 38.2–61.8% of AD |
     | Elliott wave 3/5 entry | wave-3/5 start | beyond the wave-1/4 limit / 1.618 projection |
     | SMC sweep + CHoCH + FVG | FVG retest | beyond the sweep extreme / opposite liquidity |
     | Donchian/session breakouts | breakout | breakout rules |
     | Candlestick reversal | reversal candle at confluence | candle extreme / next level |

     Every generated setup must still pass min RR and the full ADVISORY decision profile.

     (TAA-306 decision) A stop beyond the pattern extreme with a measured-move target gives RR = H/(H + ε) < 1
     for M/W, H&S and boundary breaks, so those setups could never pass min RR. Their default stop is therefore
     the **nearer** of the pattern's invalidation and 1.5 ATR (`stop_mode: nearer`); `stop_mode: invalidation`
     restores the table's rule. The Donchian/session breakouts default to the nearer stop too (the Donchian
     invalidation is the channel middle). Details: `docs/STRATEGIES.md`.
- **Setup strength = confluence score (deterministic, `confluence.py`):**
  - Within a family, supporting evidence combines with **diminishing returns** (noisy-OR: `1 − Π(1 − w·q)`), so five
    oscillators don't count five times.
  - Families are summed with family weights.
  - Conflicting evidence subtracts with a penalty factor; the strategy's own core conditions are included.
  - The result is clipped to 0–100. Weights are documented in `docs/PATTERNS.md`.
- **Win probability with attribution (upgrades TAA-6B2):**
  - **Baseline:** the hierarchical bucket model (§A26).
  - **Evidence model:**
    - **L2-regularized logistic regression** (numpy IRLS, no extra dependency), trained per strategy family ×
      asset class, with a pooled fallback.
    - Features: `quality × alignment` per detector, number of supporting families, RR band, session, volatility
      regime, HTF alignment.
    - Trained on LIVE + REPLAY outcomes, with replay down-weighted.
  - **Model selection:** walk-forward CV (Brier score, log loss). The evidence model is used only when it beats the
    bucket model out of sample; otherwise the bucket p is shown and per-theory contributions read "needs more history".
  - **Attribution:** **Shapley values** in probability space (seeded permutation sampling) split
    `p − base rate` exactly across the active evidence. Example: base rate 34% (strategy, RR 2.0, London session)
    → Fibonacci 61.8% +7, W-pattern neckline break +5, H1 uptrend +4, bearish RSI divergence −3 → **47%**.
  - **Per-theory track record:** each evidence row also shows its standalone hit rate when present (by asset class
    and TF) with n, Wilson CI and lift vs the base rate.
- **Alert content:**
  - The push shows the top 3 contributions, e.g. "Reasons: Fibonacci 61.8% +7% · W pattern +5% · H1 uptrend +4%".
  - The Opportunities page shows the full breakdown: contribution bars, conflicting evidence, each theory's record,
    and "show on chart".
  - The chart draws the evidence: fib levels, necklines, triangle/wedge lines, XABCD, Elliott labels, FVG boxes,
    S/R zones.
- **Theory scoreboard:** shadow/replay outcomes are aggregated per detector and family × asset class × TF (hit rate,
  expectancy, lift, n). This shows which theories actually work on which symbols. Theories that add nothing get ~0
  weight automatically, so the % reflects measured value, not popularity.
- **Storage:**
  - `opportunity_evidence` rows: opportunity_id, detector_id, family, direction, quality, supports, contribution_pp,
    standalone stats, key levels JSON.
  - `evidence_model_versions`: coefficients, CV metrics, training window.
  - Both are replicated to the cloud.

## A30. User-selectable theories, personalization & subscription-ready structure (rev. 2 follow-up 7)

**Principle: compute once per market, personalize per user.** The engine computes market facts: evidence,
opportunities, windows, shadow outcomes. A cloud **personalizer** turns them into each user's view and alerts,
according to that user's theory selection, preferences, account profile and **entitlements**. Today there is one
user (the owner). The data model, enforcement points and APIs are multi-user and plan-aware from day one, so
subscriptions later are configuration plus billing, not a rewrite.

- **Theory & condition selection** (per user, `TheoryPreferences`):
  - Family toggles and per-detector toggles; parameter overrides within safe bounds (e.g. fib level set, pattern
    tolerance).
  - Which pattern-based strategies may alert.
  - **Minimum supporting theories N:** alert only when ≥ N distinct families support the trade.
  - **Conflict policy:** ignore / penalize / block on a strong conflict.
  - **Presets:** "All", "Classic TA", "Price action only", "Fibonacci & harmonics", "Trend following".
  - Changes apply from the next bar. Each alert snapshots the selection it was evaluated with.
- **Compute only what is selected:**
  - The engine runs only the **union** of detectors and strategies required by active users' selections ∩ their
    entitlements. With a single user that is exactly that user's selection.
  - A dependency graph auto-enables internal prerequisites, e.g. Elliott needs zigzag + Fibonacci.
  - The union reaches the engine via `advisory-config` (compute requirements).
  - Per-detector timing metrics show the compute cost.
- **Per-user scoring with a subset of theories:**
  - Setup strength (confluence) is recomputed over only the user's enabled families.
  - Evidence-model win probability uses the user's enabled features; disabled detectors are **neutrally imputed**
    (training mean, documented) and contribute 0.
  - Explanations list only enabled theories.
  - Per-user accuracy views filter shadow outcomes to the alerts that user would have received, using the snapshotted
    selection.
- **Personalizer (cloud worker, pure library `app/advisory/personalize.py`)**, per market opportunity × user:
  1. Entitlements.
  2. Theory subset → setup strength, probability, contributions.
  3. Metric, x and minimum supporting theories.
  4. User windows, quiet hours and rate limits → user-level window end and badge.
  5. Lot, risk and reward money from the user's **account profile**:
     - owner: exact engine/MT5 sizing
     - others: spec-based calculator using replicated specs + conversion quotes
  6. User alert record → TH/EN push + in-app notification.

  It also computes a **per-user suitability ranking** from shared symbol metrics + the user's account profile, and
  per-user hypothetical P/L as `R outcome × the user's risk money at alert time`.
- **Entitlements & plans** (structure now, billing later):
  - Tables:

    | Table | Purpose |
    |---|---|
    | `plans` | code, TH/EN names, typed features and limits (below) |
    | `subscriptions` | user, plan, status, period end, provider, provider ref |
    | `entitlement_overrides` | per-user exceptions |
    | `usage_counters` | alerts per day, backtests per month, ... |

  - Plan features and limits: allowed detector families/strategies, asset classes, max watchlist symbols and lists,
    alerts per day, AI narratives, shadow-history days, backtest jobs per month, data export, API access.
  - Typed keys in code (`Feature.*`, `Limit.*`), never string literals scattered around.
  - `EntitlementService.resolve(user)` is enforced at four points: the API (options locked in the UI), the
    personalizer, worker quotas, and the engine compute union.
  - Seeded plans: **OWNER** (unlimited, assigned to you). FREE/PRO templates exist but are inactive.
  - `BillingProvider` interface (Stripe first candidate, R33) plus a signed-webhook design. **Not implemented in M1.**
  - **Compliance gate:** `SUBSCRIPTIONS_ENABLED=false` by default. While false, every subscription and billing route
    is unreachable (tested). `docs/COMPLIANCE.md` lists the legal questions (Thai SEC advisory licensing, PDPA) to
    resolve with counsel before enabling (R32).
- **Multi-tenant readiness & security:**
  - Roles: **OWNER** (everything, including controls and the kill switch), **SUBSCRIBER** (advisory features only;
    never control commands, never the owner's account, positions, decisions or trades), **ADMIN** (support, no trading
    controls).
  - Every user-owned row is scoped by `user_id` through one authorization dependency, backed by cross-tenant (IDOR)
    tests.
  - Per-plan API and push rate limits; PDPA-ready export/delete of a user's data.
- **Account profiles (`account_profiles`):** source LINKED_ENGINE (owner: live MT5 equity/balance/leverage) or MANUAL
  (equity, currency, leverage, risk %), used for lot sizing and suitability.
- **Settings pages (TH/EN):**
  - **Theories & Conditions (ทฤษฎีและเงื่อนไข):**
    - family cards with toggles, expandable per-detector toggles
    - objectivity-tier badge, short explanation + diagram
    - **theory scoreboard stats** (hit rate, lift, n per asset class) to help you choose
    - presets, minimum supporting theories, conflict policy, pattern-strategy toggles
    - advanced parameters with bounds and "reset"
    - plan-locked items show a lock (future)
  - **Account profile (บัญชีของฉัน):** linked MT5 values for the owner, manual form for others.
  - **Plan & usage (แพ็กเกจและการใช้งาน):** current plan, entitlements, usage. Billing buttons stay hidden while
    subscriptions are disabled.
  - **Users & plans (owner admin, minimal):** list users, assign plans, overrides.

## A31. Trading profile & entry plans (rev. 3)

**Goal:** alerts carry numbers that match how *this* user trades: how much risk they take, how they split
entries, and how selective they are. In Milestone 1 the profile shapes only alert content and thresholds; it
never sends orders.

- **`TradingProfile`** (per user, authoritative in the cloud, edited in the PWA; `config.yaml` →
  `advisory.trading_profile` is the fallback when no cloud is configured). Shared model in
  `app/advisory/preferences.py` (TAA-6B1).
  - **Style slider 0–100**, defensive → offensive. Five anchor presets; values in between are interpolated
    linearly. Any field the user sets explicitly overrides the slider and is shown as "custom".

    | Parameter | 0 very defensive | 25 | 50 balanced | 75 | 100 very offensive |
    |---|---|---|---|---|---|
    | Risk per signal, all entries combined (% of equity) | 0.25 | 0.5 | 0.75 | 1.0 | 1.5 |
    | Portfolio heat: open risk of all positions (%) | 0.5 | 1.0 | 2.0 | 3.0 | 4.0 |
    | Max concurrent positions | 1 | 2 | 3 | 4 | 5 |
    | Max daily loss (%) | 1.0 | 1.5 | 2.0 | 3.0 | 4.0 |
    | Min RR | 2.5 | 2.0 | 1.5 | 1.3 | 1.2 |
    | Min win probability | 62 % | 58 % | 55 % | 52 % | 50 % |
    | Min supporting families (N, §A30) | 4 | 3 | 2 | 2 | 1 |
    | Conflict policy (§A30) | block | block | penalize | penalize | ignore |
    | Require higher-timeframe alignment | yes | yes | yes | no | no |

  - Other fields:
    - holding style: scalp / day / swing, which sets the alert timeframes and the signal lifetime
    - max signals per day
    - avoid news windows (on/off)
    - hold over the weekend (on/off)
    - stop placement: structure-based or ATR-based
  - **Safety:**
    - Hard ceilings (`CEILING_*` in `app/config.py`) always apply, whatever the slider says.
    - The win-probability threshold never goes below break-even `(1 + c)/(1 + RR)` + 2 pp, and EV must be > 0.
    - In Milestone 2 the engine trades with **min(profile, local `RiskConfig`)**. A cloud profile can only make
      the owner's trading more conservative, never less: risk-increasing changes are never accepted remotely
      (§A13, §A20).
- **`EntryPlan` (splitting an entry, "แบ่งไม้").** Every alert carries an order plan built from the user's
  preferences:
  - **`lot_unit`**: the lot per tap in the MT5 app (≥ the broker's `volume_step`). Every order is a whole
    number of units, and the alert says how many taps: "3 × 0.02".
  - **Modes:**
    - `SINGLE`
    - `SAME_PRICE`: *k* orders at one price with staggered take-profits (1R, 2R, final TP); the stop moves to
      break-even after TP1 (§A11).
    - `SCALE_IN`: entry 1 at the signal; later entries as limit orders at `spacing_atr` × ATR or at the
      setup's 38.2/50/61.8 % retracements; one shared stop.
  - **Weights:** `EQUAL`, `FRONT_LOADED` (3:2:1), `BACK_LOADED` (1:2:3). Back-loaded scale-in averages into an
    adverse move and is labelled as such.
  - **Sizing** (extends §A9; TAA-401). Every part is sized against the stop:
    1. `u = budget / Σ wᵢ · (loss_per_lotᵢ + costᵢ)`
    2. `lotᵢ = floor_to_unit(wᵢ · u)`
    3. A part below `volume_min` drops the deepest part, then recompute.
    4. If a single part is still below `volume_min`, the result is `RISK_BELOW_MIN_LOT`.
    5. Never round up. The risk with **every part filled** stays within the per-signal budget (property-tested).
  - **Portfolio heat** (TAA-402): loss-to-SL of every open position, including manual ones (magic 0), plus the
    new plan must stay within the heat limit. A position without a stop has unknown risk: the alert carries a
    warning (fail closed).
  - **Alert content:**
    - the orders: market or limit, lot, price, taps
    - the stop and each take-profit
    - risk money per order and in total, as % of equity
    - portfolio heat after opening
- **Where it plugs in:**
  - the ADVISORY decision profile and the personalizer (§A30, steps 3 and 5: thresholds, N, conflict policy,
    sizing plan, heat)
  - TAA-401 / 402 (sizing, heat)
  - TAA-6B1 (models)
  - TAA-8A4 (personalizer)
  - TAA-810 (push content)
  - TAA-922 (the "บุคลิกการเทรด / Trading profile" page: slider with live numbers, per-field overrides, entry-plan
    editor with an example lot breakdown)
  - TAA-406 (M2 min-rule)
- Shadow trades (§A27) keep measuring the primary entry in R; plan-level hypothetical P/L can be added later
  without changing stored outcomes.

## A22. Delivery plan

- **Milestone 1** (never sends broker orders): Phases 0–11 plus advisory Phases 6A–6C.
  - **Execution order:** 0 ✓ → 1 ✓ (+ TAA-110 fix) → 2 → **2A** (evidence engine) → 3 → 4 → 5 → 6 →
    **6A → 6B → 6C** → 7 → 8 → **8A** (personalization & entitlements) → 9 → 10 → 11.
  - **Afterwards I stop for your review.** You can ask me to pause at any phase boundary.
- **Milestone 2** (after review): Phases 12–14, covering DEMO execution, the AI layer (now including AI on advisory,
  TAA-1305) and LIVE readiness. LIVE stays disabled by default.
- Tickets, checklists and dependencies are in Part B. `docs/TICKETS.md` is updated as each item completes.
- **First steps after approving rev. 2:**
  1. Insert §A25–A30 and R22–R33 into `docs/PLAN.md`, and update the context/decisions.
  2. Add the new phases/tickets (2A, 6A–6C, 8A, 9 additions) and the amended checklist items to `docs/TICKETS.md`,
     keeping Phase 0–1 ticks.
  3. Extend `scripts/tickets.py` to accept IDs like `TAA-2A1` / `TAA-8A4` and phase names like "Phase 2A".
  4. Save the new decisions to memory.
  5. Implement TAA-110, then continue with Phase 2.

## A23. Verification

- **Quality gates:**
  - `pytest` (unit, property-based with hypothesis, integration with FakeMT5, backtest golden files, web API)
  - coverage ≥ 90% for `risk/`, `execution/`, `engine/decision_engine.py` and `security/`
  - `ruff`, `mypy` (strict on core, risk and execution), `pip-audit`, `bandit`, gitleaks
  - `npm run lint && npm test && npm run build`
- **Look-ahead test:** mutating future bars must not change any past indicator value or decision.
- **Backtest determinism:** two runs with the same seed must produce an identical summary hash.
- **`python -m app.cli doctor`**, run read-only against the FBS terminal: connection, account verification, server-time
  offset, symbol specs, maxbars, Algo Trading state, `order_calc_profit` sign.
- **Paper soak** (≥ 1 trading week on FBS with the investor password):
  - signals, decisions and paper trades appear in the PWA
  - zero broker-order calls, by construction and confirmed by the audit trail
  - the kill-switch file blocks entries within one loop while monitoring continues
  - closing the terminal trips CONNECTION and then auto-recovers
  - a restart mid-candle produces no duplicate signal
  - the daily-loss breaker fires with a lowered threshold
- **Cloud:**
  - forged signatures, stale timestamps and reused nonces are rejected
  - an engine stop produces an ENGINE_OFFLINE push within 90 s
  - a remote FLATTEN without a valid TOTP is rejected by the engine
  - Lighthouse PWA and accessibility checks pass
  - push works on Android, desktop and installed iOS
- **Railway:** `railway config plan` is clean, healthchecks are green, and migrations run pre-deploy.
- **Advisory (rev. 2):**
  - **Ranking:** a property test shows that raising equity never lowers S1 and never turns G2 from pass to fail. A
    small-account fixture ($100, 0.5% risk) excludes XAUUSD with a correct "needs equity ≥ $Z" figure. Leverage-tier
    changes do not trip ACCOUNT_CHANGE.
  - **Sessions:** London/New York boundaries stay correct across the March/October DST weeks, when US and EU switch
    on different dates.
  - **Calibration:** on synthetic outcomes with a known p, the posterior recovers p within its CI. Thin data shows
    "insufficient data" and never produces an alert in WIN_PROBABILITY mode.
  - **Scanner:** each bar creates exactly one opportunity per strategy/symbol/side, including across restarts. An alert
    fires only when metric ≥ x and all window rules pass. A 60-symbol scan keeps monitor-loop latency under budget.
  - **Lifecycle:** with a manual clock, an opportunity moves ACTIVE → EXPIRED at the earliest window end, with the right
    reason. Price drift produces INVALIDATED. A matching manual position produces FOLLOWED.
  - **Shadow trades:** a known price path resolves TP/SL correctly. A same-bar SL+TP case is decided by ticks
    (FakeMT5 ticks), otherwise pessimistically. P/L equals `calc_profit` at the snapshotted lot. Catch-up after a
    simulated outage gives the same result as uninterrupted tracking.
  - **Paper soak addition:** over one week of monitoring, opportunities, expiry badges, shadow outcomes and accuracy
    stats appear in the PWA in TH and EN.
  - **Evidence:**
    - Each detector has golden synthetic series (a drawn W, H&S, triangle, Bat, 5-wave impulse...) that it must
      detect, and near-miss series it must reject.
    - The look-ahead harness mutates future bars for every detector.
    - Shapley contributions sum to `p − base rate` (tolerance 1e-9 with a fixed seed).
    - Double-counting control: duplicating a detector, or adding a perfectly correlated twin, does not raise setup
      strength beyond the family cap.
    - The evidence model is used only when walk-forward Brier beats the bucket model.
  - **Selection, personalization & entitlements:**
    - Disabled detectors are never executed (per-detector call counters stay 0); the engine computes only the union.
    - Per-user setup strength, probability and explanations use only enabled theories; minimum supporting theories
      gate alerts.
    - **Single-user equivalence:** the owner's personalized alerts equal the scenario computed end-to-end.
    - Cross-tenant (IDOR) tests: a SUBSCRIBER cannot read owner trading data or call control endpoints.
    - Entitlement limits are enforced at the API, personalizer and worker.
    - Subscription/billing routes return 404 while `SUBSCRIPTIONS_ENABLED=false`.

## A24. Known limitations & risks

- No profitability claim; the example strategy is a demonstration. Backtests do not predict results; overfitting is a real risk.
- Weekend and news gaps can jump stops. A broker-side SL limits losses but cannot eliminate them.
- **Non-positive prices** (WTI front-month futures settled at −37.63 USD on 2020-04-20): a bar with a low ≤ 0 is
  invalid data. Live candles flag the frame `INVALID_OHLC`, quotes with a bid or ask ≤ 0 are invalid and trip the
  INVALID_PRICE breaker; backtests flag any bar window that contains such a print. Either way new entries are
  rejected (`DATA_INVALID`) while it is in the window. Open positions keep being valued with linear P/L (correct
  for negative prices; simulated margin uses |price|), and a stop gapped through fills at the open, so the
  recorded loss can be many R. Sizing cannot protect against that tail; only the exposure caps (heat, margin,
  effective leverage, per-symbol `max_lot`) and avoiding expiry-linked energy CFDs around contract rollover can.
- MT5 time semantics are not officially documented, so they are verified at runtime. The Python API has no session
  schedule or calendar, so both are config-based.
- A PC-hosted engine depends on the PC staying on. Web Push is best-effort (especially on iOS); the dashboard is the
  source of truth.
- Leveraged FX/CFD trading is high risk. Check local regulations and tax obligations.
- **Advisory caveats (rev. 2):**
  - The win probability is an estimate from past setups, not a promise. It is shown with sample size, CI, random
    baseline and break-even.
  - Shadow P/L is hypothetical: entry at signal time, no requotes, partial fills or real slippage.
  - Replay statistics are in-sample. Ranking and alerts are advice; the user decides.
  - Scanning many symbols (especially stocks) adds terminal load, so the monitored set is capped and the ranking runs
    in batches.
  - Academic evidence for chart patterns is weak and inconsistent (R29). Elliott counts are ambiguous by nature (R31)
    and are labelled heuristic.
  - "Every theory" means an extensible catalog of rule-definable methods. Methods that cannot be stated as explicit
    rules are not invented.

**Sources:** pypi.org/project/MetaTrader5 · mql5.com/en/docs/python_metatrader5 (initialize, order_send, order_check,
order_calc_profit, symbol_info, account_info, terminal_info) · mql5.com/en/docs/constants/errorswarnings/enum_trade_return_codes ·
mql5.com/en/docs/constants/tradingconstants/orderproperties · mql5.com/en/forum/515951 · mql5.com/en/forum/516531 ·
fbs.com/trading/trading-hours · fbs.helpcenter.io (login/servers) · developers.line.biz (LINE Notify end of life) ·
docs.railway.com (infrastructure-as-code, config-as-code, private-networking, variables, deployment-regions, cli/ssh,
guides/sse-vs-websockets) · iOS Web Push requirements (pushpad, OneSignal docs) · github.com/web-push-libs/pywebpush ·
github.com/tradingview/lightweight-charts (license) · TA-Lib / pandas-ta-classic project pages ·
(rev. 2) mql5.com/en/docs/python_metatrader5/mt5symbolsget_py · mql5.com/en/docs/python_metatrader5/mt5copyticksrange_py ·
fbs.com/trading/margin-and-leverage (equity-tier and instrument leverage) · developer.mozilla.org (Badging API,
ServiceWorkerRegistration.showNotification) · caniuse.com/wf-badging.

