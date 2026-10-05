"""The engine's cloud-sync runtime: outbox, signed client, sender thread, command poller and the
advisory-config and risk-profile clients (PLAN §A13, §A33; TAA-701/704/707/710).

Built only when ``sync.enabled`` is true (config loading then requires ``CLOUD_BASE_URL``, ``ENGINE_ID`` and
``ENGINE_HMAC_SECRET``). Without it, the engine runs exactly as before and nothing leaves the machine.
"""

from __future__ import annotations

import logging
import queue
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import Settings
from app.core.clock import Clock
from app.core.errors import ConfigError
from app.security.hmac_auth import Signer, check_secret
from app.storage.database import Database
from app.storage.repositories import EngineStateRepository
from app.sync.advisory_config import AdvisoryConfigClient
from app.sync.client import CloudClient
from app.sync.commands import CommandPoller
from app.sync.outbox import Outbox, OutboxSender, SenderThread
from app.sync.risk_profile import RiskProfileClient

log = logging.getLogger(__name__)


@dataclass
class SyncRuntime:
    outbox: Outbox
    client: CloudClient
    sender: OutboxSender
    thread: SenderThread
    inbox: queue.Queue[dict[str, Any]] = field(default_factory=queue.Queue)
    poller: CommandPoller | None = None  # remote commands; processed on the engine loop
    advisory: AdvisoryConfigClient | None = None  # the users' compute requirements (TAA-707)
    risk_profile: RiskProfileClient | None = None  # the owner's trading-profile limits (TAA-710)

    @classmethod
    def from_settings(
        cls, settings: Settings, db: Database, clock: Clock, *, http: httpx.Client | None = None
    ) -> SyncRuntime:
        env, cfg = settings.env, settings.config.sync
        if not (env.CLOUD_BASE_URL and env.ENGINE_ID and env.ENGINE_HMAC_SECRET):
            raise ConfigError("sync needs CLOUD_BASE_URL, ENGINE_ID and ENGINE_HMAC_SECRET")
        signer = Signer(env.ENGINE_ID, check_secret(env.ENGINE_HMAC_SECRET.get_secret_value()), clock)
        client = CloudClient(env.CLOUD_BASE_URL, signer, timeout=cfg.request_timeout_seconds, http=http)
        outbox = Outbox(db, clock, cfg)
        sender = OutboxSender(outbox, client.post_gzip, env.ENGINE_ID, clock)
        inbox: queue.Queue[dict[str, Any]] = queue.Queue()
        poller = CommandPoller(client.get_json, inbox, poll_seconds=cfg.command_poll_seconds)
        advisory = AdvisoryConfigClient(
            client.get_conditional,
            EngineStateRepository(db, clock),
            clock,
            refresh_seconds=cfg.advisory_config_seconds,
        )
        risk_profile = RiskProfileClient(
            client.get_conditional,
            EngineStateRepository(db, clock),
            clock,
            refresh_seconds=cfg.risk_profile_seconds,
        )
        thread = SenderThread(sender, cfg.flush_interval_seconds)
        return cls(outbox, client, sender, thread, inbox, poller, advisory, risk_profile)

    def start(self) -> None:
        self.thread.start()
        if self.poller is not None:
            self.poller.start()
        for pulled in (self.advisory, self.risk_profile):
            if pulled is not None:
                pulled.start()

    def stop(self, *, final_flush: bool = False) -> None:
        """Stop the threads; with *final_flush*, make one last send attempt (the final heartbeat of a
        deliberate stop, TAA-705) before the client closes. A failed attempt stays queued for the next run."""
        if self.poller is not None:
            self.poller.stop()
        for pulled in (self.advisory, self.risk_profile):
            if pulled is not None:
                pulled.stop()
        self.thread.stop()
        if final_flush:
            try:
                self.sender.flush_once()
            except Exception:  # shutdown boundary: never block or fail the stop
                log.exception("final outbox flush failed")
        self.client.close()
