"""Emergency kill switch.

The switch is a file (default ``data/KILL_SWITCH``). Its presence alone halts new entries, which keeps
the check trivially cheap (one ``stat`` per loop) and lets an operator trigger it without any tooling:
creating the file by hand is enough. Activation/release through this class also records a DB event
and an audit entry. Release is only offered through the local CLI, never through remote commands.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from app.core.clock import Clock, SystemClock
from app.storage.audit import AuditLog
from app.storage.database import Database
from app.storage.models import KillSwitchEvent

log = logging.getLogger(__name__)


class KillMode(StrEnum):
    HALT = "HALT"  # block new entries, keep managing open positions
    FLATTEN = "FLATTEN"  # additionally close all bot positions (requires explicit permission)


@dataclass(frozen=True)
class KillState:
    active: bool
    mode: KillMode = KillMode.HALT
    reason: str = ""
    actor: str = ""
    since: str = ""


class KillSwitch:
    def __init__(
        self,
        path: Path,
        db: Database | None = None,
        audit: AuditLog | None = None,
        clock: Clock | None = None,
        flatten_allowed: bool = False,
    ) -> None:
        self.path = path
        self.db = db
        self.audit = audit
        self.clock = clock or SystemClock()
        self.flatten_allowed = flatten_allowed

    def state(self) -> KillState:
        """Read the switch. Any file content problem still counts as ACTIVE (fail-closed)."""
        if not self.path.exists():
            return KillState(active=False)
        try:
            data = json.loads(self.path.read_text(encoding="utf-8") or "{}")
            mode = KillMode(data.get("mode", KillMode.HALT))
            if mode is KillMode.FLATTEN and not self.flatten_allowed:
                mode = KillMode.HALT
            return KillState(
                True,
                mode,
                str(data.get("reason", "")),
                str(data.get("actor", "")),
                str(data.get("since", "")),
            )
        except (ValueError, OSError):
            return KillState(True, KillMode.HALT, "kill switch file present (unreadable content)", "unknown")

    def is_active(self) -> bool:
        return self.path.exists()

    def activate(self, reason: str, actor: str, source: str, mode: KillMode = KillMode.HALT) -> KillState:
        if not reason.strip():
            raise ValueError("a reason is required to activate the kill switch")
        if mode is KillMode.FLATTEN and not self.flatten_allowed:
            raise PermissionError("FLATTEN mode requires KILL_SWITCH_FLATTEN_ALLOWED=true")
        now = self.clock.now_utc().isoformat()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"mode": mode, "reason": reason, "actor": actor, "since": now, "source": source}),
            encoding="utf-8",
        )
        os.replace(tmp, self.path)  # atomic on the same volume
        self._record("ACTIVATE", mode, source, actor, reason)
        log.critical("KILL SWITCH ACTIVATED (%s) by %s via %s: %s", mode, actor, source, reason)
        return self.state()

    def release(self, reason: str, actor: str, source: str = "cli") -> None:
        if source != "cli":
            raise PermissionError("the kill switch can only be released from the local CLI")
        if not reason.strip():
            raise ValueError("a reason is required to release the kill switch")
        previous = self.state()
        if self.path.exists():
            self.path.unlink()
        self._record("RELEASE", previous.mode, source, actor, reason)
        log.warning("kill switch released by %s: %s", actor, reason)

    def _record(self, action: str, mode: KillMode, source: str, actor: str, reason: str) -> None:
        if self.db is not None:
            with self.db.session() as sess:
                sess.add(
                    KillSwitchEvent(
                        ts_utc=self.clock.now_utc(),
                        action=action,
                        mode=mode,
                        source=source,
                        actor=actor,
                        reason=reason,
                    )
                )
        if self.audit is not None:
            self.audit.append(
                f"kill_switch.{action.lower()}", actor, {"mode": mode, "source": source, "reason": reason}
            )
