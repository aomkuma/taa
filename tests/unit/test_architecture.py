"""Architecture rules enforced as tests (see docs/CODING_STANDARDS.md §2-§3).

These turn conventions that used to be honor-system into build failures:

1. Layering: a module may import only modules of the same or a lower layer (``LAYERS``).
2. Only ``app/broker/`` may import the ``MetaTrader5`` package.
3. Cloud processes (``app.web``, ``app.worker``) never import live-broker modules.
4. Broker order functions (``order_send``/``order_check``) are referenced only inside ``app/broker/``.
5. Domain code never reads the wall clock directly; time comes from an injected ``Clock``.
6. Analysis and strategy code is pure: no broker services, storage, secrets, settings loaders or environment.

Changing ``LAYERS`` or an allow-list is a design decision: update docs/CODING_STANDARDS.md in the same change.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"

# Longest matching prefix wins. Same-layer imports are allowed; importing a higher layer is a violation.
LAYERS: dict[str, int] = {
    # 0: foundation (pure domain types/constants usable everywhere)
    "app": 0,
    "app.core": 0,
    "app.broker.mt5_constants": 0,
    "app.broker.retcodes": 0,
    "app.broker.symbol_groups": 0,
    "app.broker.models": 0,
    "app.market_data.data_models": 0,
    # 1: configuration, secrets, logging
    "app.security": 1,
    "app.config": 1,
    "app.logging_config": 1,
    # 2: persistence
    "app.storage": 2,
    # 3: broker access (MT5 client, gateway, symbol/account services, FakeMT5)
    "app.broker": 3,
    # 4: market data services, sessions/news
    "app.market_data": 4,
    "app.news": 4,
    # 5: pure analysis
    "app.indicators": 5,
    "app.evidence": 5,
    # 6: strategies
    "app.strategy": 6,
    # 7: risk and the decision pipeline
    "app.risk": 7,
    "app.engine.decision_engine": 7,
    # 8: execution and simulation
    "app.execution": 8,
    "app.backtest": 8,
    # 9: higher-level libraries
    "app.advisory": 9,
    "app.analytics": 9,
    "app.ai": 9,
    "app.learning": 9,
    "app.monitoring": 9,
    # 10: engine runtime and sync
    "app.engine": 10,
    "app.sync": 10,
    # 11: cloud processes
    "app.web": 11,
    "app.worker": 11,
    # 12: entry points
    "app.cli": 12,
    "app.main": 12,
}

# Modules the cloud processes must never import directly (they would need a local MT5 terminal).
LIVE_BROKER_MODULES = (
    "app.broker.mt5_client",
    "app.broker.factory",
    "app.broker.fake_mt5",
    "app.broker.gateway",
)
CLOUD_PACKAGES = ("app.web", "app.worker")

# Wall-clock reads allowed only here (the Clock implementation and ORM column defaults).
WALL_CLOCK_ALLOWED = {"app.core.clock", "app.storage.models.base"}
WALL_CLOCK_CALLS = {("datetime", "now"), ("datetime", "utcnow"), ("date", "today"), ("time", "time")}

ORDER_FUNCTIONS = ("order_send", "order_check")

# Pure analysis/strategy packages: they see market data as values, never a broker session, a database or a
# credential (layer-0 data models such as app.market_data.data_models stay allowed).
PURE_PACKAGES = ("app.indicators", "app.evidence", "app.strategy")
PURE_FORBIDDEN_MODULES = ("app.broker", "app.storage", "app.security", "app.market_data")
PURE_FORBIDDEN_NAMES = {"EnvSettings", "Settings", "load_settings", "environ", "getenv", "keyring"}


@dataclass(frozen=True)
class Module:
    name: str
    path: Path
    tree: ast.Module


def _module_name(path: Path) -> str:
    parts = list(path.relative_to(ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _load_modules() -> list[Module]:
    modules = []
    for path in sorted(APP.rglob("*.py")):
        if "migrations" in path.parts:
            continue
        modules.append(Module(_module_name(path), path, ast.parse(path.read_text(encoding="utf-8"))))
    return modules


MODULES = _load_modules()
MODULE_NAMES = {m.name for m in MODULES}


def _type_checking_nodes(tree: ast.Module) -> set[int]:
    """Nodes inside ``if TYPE_CHECKING:`` blocks (annotation-only imports create no runtime dependency)."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test = node.test
            name = test.id if isinstance(test, ast.Name) else getattr(test, "attr", None)
            if name == "TYPE_CHECKING":
                for sub in node.body:
                    ids.update(id(n) for n in ast.walk(sub))
    return ids


def _imports(module: Module) -> list[tuple[str, int]]:
    """(imported module, line) for every runtime import, resolving ``from pkg import submodule``."""
    skip = _type_checking_nodes(module.tree)
    found: list[tuple[str, int]] = []
    for node in ast.walk(module.tree):
        if id(node) in skip:
            continue
        if isinstance(node, ast.Import):
            found.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for alias in node.names:
                candidate = f"{node.module}.{alias.name}"
                found.append((candidate if candidate in MODULE_NAMES else node.module, node.lineno))
    return found


def _layer(name: str) -> int | None:
    best = None
    for prefix, layer in LAYERS.items():
        if (name == prefix or name.startswith(prefix + ".")) and (best is None or len(prefix) > len(best[0])):
            best = (prefix, layer)
    return None if best is None else best[1]


def _where(module: Module, line: int) -> str:
    return f"{module.path.relative_to(ROOT)}:{line}"


def test_every_app_module_has_a_layer() -> None:
    missing = sorted(m.name for m in MODULES if _layer(m.name) is None)
    assert not missing, f"add these modules/packages to LAYERS: {missing}"


def test_layering() -> None:
    violations = []
    for module in MODULES:
        own = _layer(module.name)
        for target, line in _imports(module):
            if not target.startswith("app"):
                continue
            target_layer = _layer(target)
            if own is not None and target_layer is not None and target_layer > own:
                violations.append(
                    f"{_where(module, line)}: {module.name} (layer {own}) imports {target} (layer {target_layer})"
                )
    assert not violations, "layering violations:\n" + "\n".join(violations)


def test_only_broker_imports_metatrader5() -> None:
    violations = [
        f"{_where(m, line)}: {m.name} imports {target}"
        for m in MODULES
        if not m.name.startswith("app.broker")
        for target, line in _imports(m)
        if target == "MetaTrader5" or target.startswith("MetaTrader5.")
    ]
    assert not violations, "MetaTrader5 may only be imported inside app/broker:\n" + "\n".join(violations)


def test_cloud_processes_do_not_import_live_broker() -> None:
    violations = [
        f"{_where(m, line)}: {m.name} imports {target}"
        for m in MODULES
        if m.name.startswith(CLOUD_PACKAGES)
        for target, line in _imports(m)
        if target.startswith(LIVE_BROKER_MODULES)
    ]
    assert not violations, "web/worker must not touch the MT5 terminal:\n" + "\n".join(violations)


def test_order_functions_only_referenced_in_broker() -> None:
    violations = []
    for module in MODULES:
        if module.name.startswith("app.broker"):
            continue
        for node in ast.walk(module.tree):
            text = None
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value
            elif isinstance(node, ast.Attribute):
                text = node.attr
            elif isinstance(node, ast.Name):
                text = node.id
            if text in ORDER_FUNCTIONS:
                violations.append(f"{_where(module, getattr(node, 'lineno', 0))}: references {text}")
    assert not violations, "order functions are only allowed inside app/broker:\n" + "\n".join(violations)


def test_no_direct_wall_clock_in_domain_code() -> None:
    violations = []
    for module in MODULES:
        if module.name in WALL_CLOCK_ALLOWED:
            continue
        for node in ast.walk(module.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                owner = node.func.value
                owner_name = owner.id if isinstance(owner, ast.Name) else getattr(owner, "attr", None)
                if (owner_name, node.func.attr) in WALL_CLOCK_CALLS:
                    violations.append(f"{_where(module, node.lineno)}: {owner_name}.{node.func.attr}()")
    assert not violations, "inject a Clock instead of reading the wall clock:\n" + "\n".join(violations)


def _pure_violations(module: Module) -> list[str]:
    found = [
        f"{_where(module, line)}: imports {target}"
        for target, line in _imports(module)
        if target.startswith(PURE_FORBIDDEN_MODULES) and _layer(target) != 0
    ]
    for node in ast.walk(module.tree):
        if isinstance(node, ast.ImportFrom):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.Attribute):
            names = [node.attr]
        elif isinstance(node, ast.Name):
            names = [node.id]
        else:
            continue
        found.extend(
            f"{_where(module, getattr(node, 'lineno', 0))}: uses {n}"
            for n in names
            if n in PURE_FORBIDDEN_NAMES
        )
    return found


def test_strategies_and_analysis_are_isolated() -> None:
    violations = [v for m in MODULES if m.name.startswith(PURE_PACKAGES) for v in _pure_violations(m)]
    assert not violations, "strategy/analysis code must stay pure:\n" + "\n".join(violations)


# --------------------------------------------------------------------- self-tests of the checker
@pytest.mark.parametrize(
    ("name", "layer"),
    [
        ("app.core.clock", 0),
        ("app.broker.mt5_constants", 0),
        ("app.broker.gateway", 3),
        ("app.market_data.data_models", 0),
        ("app.market_data.candle_service", 4),
        ("app.engine.decision_engine", 7),
        ("app.engine.orchestrator", 10),
        ("app.cli.doctor", 12),
    ],
)
def test_layer_lookup(name: str, layer: int) -> None:
    assert _layer(name) == layer


def test_checker_detects_violations() -> None:
    bad = Module(
        "app.indicators.fake",
        APP / "indicators" / "fake.py",
        ast.parse(
            "import MetaTrader5\n"
            "from app.engine.orchestrator import X\n"
            "from datetime import datetime\n"
            "now = datetime.now()\n"
            "client.call('order_send', {})\n"
        ),
    )
    imports = [t for t, _ in _imports(bad)]
    assert "MetaTrader5" in imports
    assert _layer("app.engine.orchestrator") > _layer(bad.name)  # type: ignore[operator]
    calls = [n for n in ast.walk(bad.tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
    assert any((getattr(c.func.value, "id", None), c.func.attr) in WALL_CLOCK_CALLS for c in calls)  # type: ignore[attr-defined]
    assert any(isinstance(n, ast.Constant) and n.value == "order_send" for n in ast.walk(bad.tree))


def test_isolation_checker_detects_violations() -> None:
    bad = Module(
        "app.strategy.fake",
        APP / "strategy" / "fake.py",
        ast.parse(
            "from app.broker.gateway import MarketDataGateway\n"
            "from app.market_data.candle_service import CandleService\n"
            "from app.market_data.data_models import SymbolSpec\n"
            "from app.config import load_settings\n"
            "import os\n"
            "key = os.environ['MT5_PASSWORD']\n"
        ),
    )
    found = _pure_violations(bad)
    assert len(found) == 4, found
    assert not any("data_models" in v for v in found)
