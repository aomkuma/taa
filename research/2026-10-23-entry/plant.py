"""Planted-bug harness for app modules (SPEC.md section 4.3): each bug is a text edit of the module; the edited copy
replaces the module for one pytest run of its test file (a plugin registers it under the module's name before the
tests import it); every bug must make a test fail (CAUGHT). The repo's file is never touched.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PLUGIN = '''import importlib, importlib.util, sys
importlib.import_module("{package}")
spec = importlib.util.spec_from_file_location("{name}", r"{path}")
mod = importlib.util.module_from_spec(spec)
sys.modules["{name}"] = mod
spec.loader.exec_module(mod)
setattr(sys.modules["{package}"], "{short}", mod)
'''


def mutate(src: str, edits: list[tuple[str, str]]) -> str:
    for old, new in edits:
        n = src.count(old)
        if n != 1:
            raise ValueError(f"the bug's text occurs {n} times, not once: {old!r}")
        src = src.replace(old, new)
    return src


def run(name: str, src: str, test: Path) -> tuple[bool, str]:
    package, short = name.rsplit(".", 1)
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / f"{short}_planted.py").write_text(src, encoding="utf-8")
        (d / "plant_plugin.py").write_text(PLUGIN.format(package=package, name=name, short=short, path=d / f"{short}_planted.py"), encoding="utf-8")
        env = {**__import__("os").environ, "PYTHONPATH": f"{d};{ROOT}"}
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "-p", "plant_plugin", str(test)],
                           cwd=ROOT, capture_output=True, text=True, check=False, env=env)
        failed = re.findall(r"FAILED \S+::(\S+)", r.stdout)
        last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()[-300:]
        return r.returncode == 0, failed[0] if failed else last


def main(name: str, test: Path, bugs: list[tuple[str, list[tuple[str, str]]]]) -> None:
    path = ROOT / (name.replace(".", "/") + ".py")
    src = path.read_text(encoding="utf-8")
    ok, line = run(name, src, test)
    print(f"{path.name}: control (no bug): {'PASSED' if ok else 'FAILED'} - {line}", flush=True)
    if not ok:
        raise SystemExit("the unedited source must pass first")
    caught = 0
    for k, (label, edits) in enumerate(bugs, 1):
        ok, line = run(name, mutate(src, edits), test)
        if any(x in line for x in ("SyntaxError", "IndentationError", "source_to_code")):
            print(f"  {k:2d}. {label}: INVALID EDIT (the bug does not compile - not a catch)", flush=True)
            continue
        caught += not ok
        print(f"  {k:2d}. {label}: {'CAUGHT by ' + line if not ok else 'MISSED'}", flush=True)
    print(f"caught {caught} / {len(bugs)}")


SCRIPT_PLUGIN = '''import importlib.util, sys
sys.path.insert(0, r"{here}")
spec = importlib.util.spec_from_file_location("{name}", r"{path}")
mod = importlib.util.module_from_spec(spec)
sys.modules["{name}"] = mod
spec.loader.exec_module(mod)
'''


def run_script(name: str, here: Path, src: str, test: Path) -> tuple[bool, str]:
    """As run(), for a research module outside a package: the edited copy is registered as ``name``."""
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / f"{name}_planted.py").write_text(src, encoding="utf-8")
        (d / "plant_plugin.py").write_text(SCRIPT_PLUGIN.format(here=here, name=name, path=d / f"{name}_planted.py"), encoding="utf-8")
        env = {**__import__("os").environ, "PYTHONPATH": f"{d};{ROOT}"}
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "-p", "plant_plugin", str(test)],
                           cwd=ROOT, capture_output=True, text=True, check=False, env=env)
        failed = re.findall(r"FAILED \S+::(\S+)", r.stdout)
        last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()[-300:]
        return r.returncode == 0, failed[0] if failed else last


def main_script(path: Path, test: Path, bugs: list[tuple[str, list[tuple[str, str]]]]) -> None:
    """main() for a research module outside a package (observe.py, knowledge/kb.py)."""
    name, src = path.stem, path.read_text(encoding="utf-8")
    ok, line = run_script(name, path.parent, src, test)
    print(f"{path.name}: control (no bug): {'PASSED' if ok else 'FAILED'} - {line}", flush=True)
    if not ok:
        raise SystemExit("the unedited source must pass first")
    caught = 0
    for k, (label, edits) in enumerate(bugs, 1):
        ok, line = run_script(name, path.parent, mutate(src, edits), test)
        if any(x in line for x in ("SyntaxError", "IndentationError", "source_to_code")):
            print(f"  {k:2d}. {label}: INVALID EDIT (the bug does not compile - not a catch)", flush=True)
            continue
        caught += not ok
        print(f"  {k:2d}. {label}: {'CAUGHT by ' + line if not ok else 'MISSED'}", flush=True)
    print(f"caught {caught} / {len(bugs)}")
