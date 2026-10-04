"""Engine watchdog (PLAN §A13 "Heartbeats"; TAA-705), a scheduled worker task every 10 s.

For every ACTIVE engine that has ever sent a heartbeat:

- **offline** when its last heartbeat said ``stopped`` (reason STOPPED) or none arrived for
  ``OFFLINE_AFTER`` (60 s, reason SILENT), measured on the cloud clock (``received_at``), so the engine's
  own clock does not matter
- an offline engine raises ENGINE_OFFLINE for its owner only while its markets are open by the last
  heartbeat's schedule (:func:`app.sync.heartbeat.market_open_at`): an engine switched off at the weekend
  stays quiet until its market opens, and alerts then if it is still silent
- once heartbeats resume (and the engine runs), ENGINE_BACK with the downtime

One alert per offline episode: ``watch_status`` flips ONLINE → OFFLINE → ONLINE. Engines that never made
contact are "waiting for first contact", not offline; revoked engines are ignored.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select

from app.core.clock import Clock, ensure_utc
from app.storage.database import Database
from app.storage.models import EngineHeartbeatRow, EngineRow
from app.sync.heartbeat import market_open_at
from app.sync.notifications import NotificationType, Severity, notify
from app.sync.stream import StreamLog

log = logging.getLogger(__name__)

OFFLINE_AFTER = timedelta(seconds=60)
ONLINE, OFFLINE = "ONLINE", "OFFLINE"


class EngineWatchdog:
    def __init__(self, db: Database, clock: Clock, offline_after: timedelta = OFFLINE_AFTER) -> None:
        self.db = db
        self.clock = clock
        self.offline_after = offline_after
        self.stream = StreamLog(db, clock)

    def check(self) -> list[str]:
        """One pass; returns the transitions made (``<engine>:OFFLINE`` / ``<engine>:ONLINE``)."""
        now = self.clock.now_utc()
        changes: list[str] = []
        with self.db.session() as sess:
            rows = sess.execute(
                select(EngineHeartbeatRow, EngineRow)
                .join(EngineRow, EngineRow.engine_id == EngineHeartbeatRow.engine_id)
                .where(EngineRow.status == "ACTIVE")
            ).all()
            for hb, engine in rows:
                last = ensure_utc(hb.received_at)
                reason = (
                    "STOPPED"
                    if hb.state == "stopped"
                    else "SILENT"
                    if now - last > self.offline_after
                    else ""
                )
                if reason and hb.watch_status == ONLINE:
                    if not market_open_at(hb.market_open, hb.market_change_at, now):
                        continue  # markets closed: nobody misses the engine yet
                    hb.watch_status, hb.offline_since, hb.offline_reason = OFFLINE, last, reason
                    notify(
                        sess,
                        self.stream,
                        user_id=engine.owner_user_id,
                        engine_id=engine.engine_id,
                        type_=NotificationType.ENGINE_OFFLINE,
                        severity=Severity.WARNING,
                        payload={"label": engine.label, "reason": reason, "last_seen_at": last},
                        now=now,
                    )
                    changes.append(f"{engine.engine_id}:{OFFLINE}")
                    log.warning(
                        "engine %s is offline (%s since %s)", engine.engine_id, reason, last.isoformat()
                    )
                elif not reason and hb.watch_status == OFFLINE:
                    since = ensure_utc(hb.offline_since) if hb.offline_since is not None else last
                    hb.watch_status, hb.offline_since, hb.offline_reason = ONLINE, None, ""
                    notify(
                        sess,
                        self.stream,
                        user_id=engine.owner_user_id,
                        engine_id=engine.engine_id,
                        type_=NotificationType.ENGINE_BACK,
                        severity=Severity.INFO,
                        payload={
                            "label": engine.label,
                            "offline_since": since,
                            "downtime_seconds": int((last - since).total_seconds()),
                        },
                        now=now,
                    )
                    changes.append(f"{engine.engine_id}:{ONLINE}")
                    log.info("engine %s is back", engine.engine_id)
        return changes
