# Coding standards

The conventions every change to TAA follows. They describe how the existing code is written; when in doubt, match
the surrounding code. `CLAUDE.md` holds the short version plus the commands.

## 1. Style and tooling

- Python 3.11+. `from __future__ import annotations` at the top of every module.
- **ruff** is the formatter and linter (`line-length = 110`). Run `ruff format` and `ruff check`; both must pass.
  The enabled rule families are in `pyproject.toml`; notable ones:
  - **DTZ**: no naive datetimes
  - **S**: security
  - **T20**: no `print()` outside `app/cli/` and `scripts/`
  - **PT**: pytest style
- **mypy** must pass for `app/`. `app.core`, `app.risk`, `app.execution`, `app.security` and `app.engine` require
  fully typed functions (`disallow_untyped_defs`). Avoid `# type: ignore`; when one is unavoidable, give it an
  error code.
- **bandit** must pass for `app/`.
- Comments explain *why* (a broker quirk, a safety reason, a source). Don't narrate what the code does. Module
  docstrings state the module's purpose and any non-obvious invariant.
- Never use `assert` in library code for validation; raise an explicit error instead (asserts disappear under
  `python -O`).

## 2. Safety rules (non-negotiable)

- **Fail closed.** Missing data, an inconsistent symbol spec, an unknown order state or a failed check means
  HOLD / reject / halt, never "best effort".
- **No broker orders in Milestone 1.** Never call `order_send`/`order_check`, and never construct
  `MT5Client(allow_trading=True)`.
- **Only `app/broker/` talks to MetaTrader5.** Everything else uses the `MarketDataGateway` protocol, so code
  stays testable with `FakeMT5` on any OS.
- **Risk can only be reduced remotely.** Commands from the cloud may activate the kill switch or disable things.
  Releasing, enabling or raising limits stays in local config/CLI.
- **Volumes are floored, never rounded up.** Use `app/core/decimal_utils.py` (`floor_to_step`, `round_to_tick`)
  for anything sent to or compared with the broker.
- Every stop-loss path is mandatory; there is no "no SL" option.

### Enforced by `tests/unit/test_architecture.py`

These rules fail the build when broken; they are not honor-system:

| Rule | Check |
|---|---|
| Layering | A module imports only the same or lower layers (`LAYERS` table: foundation types → config/security → storage → broker → market data → indicators/evidence → strategy → risk/decision → execution/backtest → advisory/analytics → engine/sync → web/worker → cli). Imports inside `if TYPE_CHECKING:` don't count. |
| MetaTrader5 | Only modules under `app/broker/` may import it. |
| Cloud isolation | `app.web` / `app.worker` never import `mt5_client`, `factory`, `fake_mt5` or `gateway`. |
| Order functions | `order_send` / `order_check` appear only inside `app/broker/`. |
| Wall clock | `datetime.now/utcnow`, `date.today` and `time.time` are allowed only in `app/core/clock.py` and ORM column defaults. Monotonic timers such as `time.perf_counter` are fine. |

A new package must be added to `LAYERS` (`test_every_app_module_has_a_layer` fails otherwise). Changing a layer or
an allow-list is a design decision: change the test and this section together, and say why in the change.

## 3. Time

- All datetimes are **timezone-aware UTC** (`datetime.now(UTC)` or `clock.now_utc()`). Naive datetimes are a bug.
  `ensure_utc()` rejects them.
- Inject time through the `Clock` protocol (`SystemClock` in production, `ManualClock` in tests). Never call
  `datetime.now()` / `time.time()` directly in domain code.
- MT5 epochs are **server wall-clock** time. Convert with `ServerClock.server_epoch_to_utc` /
  `server_epochs_to_utc`, and in the other direction with `utc_to_server_epoch`. Never add a fixed offset.
- Store datetimes in `UTCDateTime` columns (`app/storage/types.py`).
- Market sessions are defined in exchange-local timezones (zoneinfo), never as fixed UTC hours.

## 4. Market data, indicators and detectors

- Decisions use **closed bars only** (`CandleService.closed_candles`). Never use position 0 of
  `copy_rates_from_pos`.
- No look-ahead:
  - The value at bar *t* may depend only on bars ≤ *t*.
  - Swing-based logic uses **confirmed** pivots (k-bar lag).
  - Multi-timeframe joins align on bar **close** time.
  - Each indicator/detector gets a mutation test: changing future bars must not change past outputs.
- Indicators are pure functions on pandas/numpy without I/O. Warm-up periods yield NaN and the caller treats NaN as
  "insufficient data" (HOLD). Document the formula and conventions in `docs/INDICATORS.md`, and cross-check
  against TA-Lib (dev-only) after a burn-in.
- Evidence (rev. 2) is immutable once attached to an opportunity; later re-detection never rewrites history.
- **pandas 3:**
  - Don't assume nanosecond resolution. Convert time differences with `// pd.Timedelta(seconds=1)` or
    `.total_seconds()`, never `.asi8 / 1e9`.
  - Copy-on-Write is the default: never rely on chained assignment.

## 5. Configuration and secrets

- Non-secret parameters live in `config.yaml` models in `app/config.py` (`StrictModel`: frozen,
  `extra="forbid"`). Secrets and safety flags live in `EnvSettings`.
- **Adding a setting** means:
  1. Add the field with bounds (`Field(gt=…, le=…)`).
  2. Add cross-field checks in a `model_validator` when needed.
  3. Update `config.yaml` and/or `.env.example` with placeholders only.
  4. Write a test for valid and invalid values.
- Risk values are **percent** of equity (`0.5` = 0.5%). A value above a hard ceiling is an error, never silently
  clamped.
- Secrets are `SecretStr`. Resolve them via `app/security/secrets.py`, which registers them for log redaction.
  Never log, format or return a secret. Show account numbers only with `mask_login()`.

## 6. Errors and logging

- Raise subclasses of `TaaError` (`app/core/errors.py`). Add a new subclass when callers need to react
  differently; don't raise bare `Exception`/`ValueError` across module boundaries.
- Use `log = logging.getLogger(__name__)` with %-style arguments (`log.info("x=%s", x)`), never f-strings in
  log calls.
- Logs go through redaction automatically (`app/logging_config.py`). Bind correlation ids with
  `app.core.context.bind(...)` around work units (cycle, signal, intent, command).
- Catch broad exceptions only at process boundaries (loops, CLI, health probes), and always log them with the
  traceback.

## 7. Storage

- Models live in `app/storage/models/<area>.py` and are exported from `app/storage/models/__init__.py`, which
  Alembic autogenerate requires.
- Keep schemas portable across SQLite and PostgreSQL: use `UTCDateTime`, `JSONType`, `String(n)`, `BigInteger`
  where values may exceed 32 bits, and the naming convention from `Base`.
- Every schema change needs an Alembic revision (`--rev-id 000N`), reviewed by hand. Tests use
  `Database("sqlite://").create_all()`; `test_migrations_match_models` keeps migrations and models in sync.
- Use `Database.session()` (commit on success, rollback on error). Keep sessions short; don't hold one across
  broker calls.
- Security-relevant actions append to the audit chain (`AuditLog.append`). The audit table is append-only.

## 8. Tests

- Layout: `tests/unit`, `tests/property` (hypothesis), `tests/integration`, `tests/backtest`, `tests/web`.
- Every behavior change comes with tests; safety rules get explicit negative tests (e.g. `order_send` call count
  is 0, a forged signature is rejected, a disabled detector is never executed).
- Use `FakeMT5` + `ManualClock`. Standard instants:
  - Wednesday 2026-09-30 10:00–15:00 UTC: market open, EEST (+3)
  - Saturday 2026-10-03: FX closed, crypto open
- `FakeMT5(symbols=ALL_SYMBOLS)` covers every asset class; inject failures with `fail_next()` / `disconnect()`.
- No network in tests. Real-terminal and Postgres tests are opt-in via the `mt5` / `postgres` markers.
- Property-based tests (hypothesis) for numeric invariants: sizing never exceeds budget, volumes align to step,
  indicator bounds.

## 9. Documentation and tickets

- Docs, comments and docstrings are in English. User-facing PWA text and notifications use translation keys
  (TH/EN).
- When a design decision changes, update `docs/PLAN.md` in the same change.
- When ticket items are completed, tick them with `scripts/tickets.py` and run `sync`. Never edit the progress
  table by hand.
- Keep `docs/HANDOFF.md` current at the end of a work session (state, next step, open items).
