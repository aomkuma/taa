"""The engine's cloud-sync runtime: outbox, signed client and sender thread (PLAN §A13; TAA-701).

Built only when ``sync.enabled`` is true (config loading then requires ``CLOUD_BASE_URL``, ``ENGINE_ID`` and
``ENGINE_HMAC_SECRET``). Without it, the engine runs exactly as before and nothing leaves the machine.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import Settings
from app.core.clock import Clock
from app.core.errors import ConfigError
from app.security.hmac_auth import Signer, check_secret
from app.storage.database import Database
from app.sync.client import CloudClient
from app.sync.outbox import Outbox, OutboxSender, SenderThread


@dataclass
class SyncRuntime:
    outbox: Outbox
    client: CloudClient
    sender: OutboxSender
    thread: SenderThread

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
        return cls(outbox, client, sender, SenderThread(sender, cfg.flush_interval_seconds))

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.thread.stop()
        self.client.close()
