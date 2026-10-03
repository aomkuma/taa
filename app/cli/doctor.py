"""``python -m app.cli doctor``: read-only diagnostics of the terminal, account, server time and symbols."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path

from app.broker import mt5_constants as c
from app.broker.factory import build_read_only
from app.broker.filling import FILLING_NAMES, allowed_fillings
from app.config import Settings
from app.core.enums import Side, TradingMode
from app.market_data.server_time import verify_server_time_any
from app.security.redaction import mask_login


@dataclass
class DoctorReport:
    lines: list[str] = field(default_factory=list)
    failures: int = 0
    warnings: int = 0

    def ok(self, msg: str) -> None:
        self.lines.append(f"  [ OK ] {msg}")

    def warn(self, msg: str) -> None:
        self.warnings += 1
        self.lines.append(f"  [WARN] {msg}")

    def fail(self, msg: str) -> None:
        self.failures += 1
        self.lines.append(f"  [FAIL] {msg}")

    def section(self, title: str) -> None:
        self.lines.append("")
        self.lines.append(title)


def run_doctor(settings: Settings, *, fake: bool = False, wait_seconds: float = 10.0) -> DoctorReport:
    r = DoctorReport()
    env = settings.env
    r.section("Environment")
    r.ok(f"Python {sys.version.split()[0]}")
    if importlib.util.find_spec("tzdata") is None:
        r.fail("tzdata package missing (required for timezone rules on Windows)")
    else:
        r.ok("tzdata installed")
    if settings.mode is TradingMode.BACKTEST:
        r.warn("TRADING_MODE=BACKTEST: broker checks still run but the engine will not connect in this mode")
    if not fake:
        if importlib.util.find_spec("MetaTrader5") is None:
            r.fail("MetaTrader5 package not installed (Windows only)")
            return r
        path = Path(env.MT5_TERMINAL_PATH or "")
        (r.ok if path.exists() else r.fail)(
            f"terminal path {path} {'exists' if path.exists() else 'NOT FOUND'}"
        )

    bundle = build_read_only(settings, fake=fake)
    r.section("Connection & account")
    try:
        report = bundle.client.connect()
    except Exception as exc:
        r.fail(f"connect failed: {exc}")
        return r
    acct, term = report.account, report.terminal
    r.ok(f"connected {mask_login(acct.login)}@{acct.server} ({acct.company}) build {term.build}")
    r.ok(
        f"account type {acct.trade_mode_name}, margin mode {acct.margin_mode_name}, "
        f"currency {acct.currency}, "
        f"leverage 1:{acct.leverage}"
    )
    r.ok(
        f"balance {acct.balance:.2f} equity {acct.equity:.2f}; margin call {acct.margin_so_call:g}, "
        f"stop-out {acct.margin_so_so:g}"
    )
    for w in report.verification.warnings:
        r.warn(w)
    (r.ok if not acct.trade_allowed else r.warn)(
        "login is read-only (investor password)"
        if not acct.trade_allowed
        else "login can trade (master password)"
    )
    (r.ok if term.trade_allowed else r.warn)(f"Algo Trading button {'ON' if term.trade_allowed else 'OFF'}")
    (r.warn if term.tradeapi_disabled else r.ok)(
        f"external Python API trading {'DISABLED in options' if term.tradeapi_disabled else 'allowed'}"
    )
    need = settings.config.timeframes.warmup_bars + 10
    (r.ok if term.maxbars >= need else r.fail)(f"Max bars in chart = {term.maxbars} (need >= {need})")

    r.section("Server time")
    clock_symbol, ver = verify_server_time_any(
        bundle.gateway, settings.config.symbols.clock_symbols, wait_seconds=wait_seconds
    )
    via = f" (via {clock_symbol})" if clock_symbol else ""
    (r.ok if ver.ok else (r.warn if ver.status.value.startswith("UNVERIFIED") else r.fail))(
        f"{ver.status}{via}: {ver.detail}"
    )

    r.section("Symbols")
    for name in settings.config.symbols.allowed:
        try:
            spec = bundle.gateway.symbol_spec(name)
        except Exception as exc:
            r.fail(f"{name}: {exc}")
            continue
        problems = spec.validation_errors()
        fills = "/".join(FILLING_NAMES[f] for f in allowed_fillings(spec)) or "NONE"
        line = (
            f"{name}: digits {spec.digits}, point {spec.point:g}, tick {spec.tick_size:g} = "
            f"{spec.tick_value:g} {acct.currency}, contract {spec.contract_size:g}, vol "
            f"{spec.volume_min:g}..{spec.volume_max:g} step {spec.volume_step:g}, stops {spec.stops_level}, "
            f"freeze {spec.freeze_level}, mode {c.TRADE_MODE_NAMES.get(spec.trade_mode)}/"
            f"{c.EXECUTION_MODE_NAMES.get(spec.execution_mode)}, filling {fills}, spread {spec.spread_points}"
        )
        (r.fail if problems or fills == "NONE" else r.ok)(
            line + (f" PROBLEMS: {problems}" if problems else "")
        )
        tick = bundle.gateway.tick(name)
        if tick is not None:
            loss = bundle.gateway.calc_profit(Side.BUY, name, 1.0, tick.ask, tick.ask - 100 * spec.tick_size)
            if loss is None:
                r.fail(f"{name}: order_calc_profit returned None")
            elif loss >= 0:
                r.fail(f"{name}: order_calc_profit sign convention unexpected (loss computed as {loss})")
            else:
                r.ok(f"{name}: order_calc_profit(100 ticks against 1 lot) = {loss:.2f} {acct.currency}")
    bundle.client.shutdown()
    return r
