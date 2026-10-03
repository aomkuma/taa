"""MetaTrader 5 symbol group filter semantics (as used by ``symbols_get(group=...)``).

A group is a comma-separated list of conditions applied in order. ``*`` is a wildcard and a leading
``!`` excludes. Inclusions should precede exclusions, e.g. ``"*, !*EUR*"`` selects every symbol whose
name does not contain EUR. Matching is case-insensitive.
"""

from __future__ import annotations

from fnmatch import fnmatchcase


def match_group(name: str, group: str | None) -> bool:
    if not group or not group.strip():
        return True
    included = False
    upper = name.upper()
    for raw in group.split(","):
        cond = raw.strip()
        if not cond:
            continue
        negate = cond.startswith("!")
        pattern = (cond[1:] if negate else cond).upper()
        if fnmatchcase(upper, pattern):
            included = not negate
    return included
