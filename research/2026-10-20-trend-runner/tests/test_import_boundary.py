# ruff: noqa: S101
from __future__ import annotations

import ast
from pathlib import Path


def test_tr1_does_not_import_other_setups() -> None:
    root = Path(__file__).resolve().parents[1] / "tr1"
    banned = ("agents.dev", "agents.dev2", "agents.strategist", "plan1")
    faults: list[str] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                if any(token in name.lower() for token in banned):
                    faults.append(f"{path.name}:{node.lineno}: {name}")
    assert faults == []
