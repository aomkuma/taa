"""Advisory-config pull client: the users' compute requirements from the cloud (PLAN §A26, §A30; TAA-707).

``GET /api/v1/engine/advisory-config`` returns an :class:`app.advisory.requirements.AdvisoryConfig`, polled
every ``sync.advisory_config_seconds`` by :class:`app.sync.pull.PulledDocument` (its own thread, conditional
GET, cache in ``engine_state`` key ``advisory_config``, backoff). Without a document (``current`` is None) the
local ``config.yaml`` preferences apply. The config only decides what the advisory scanner computes and which
symbols it watches; it never touches the bot's trading universe, strategies or risk.
"""

from __future__ import annotations

from app.advisory.requirements import AdvisoryConfig
from app.sync.pull import ConditionalGet, PulledDocument

ADVISORY_CONFIG_PATH = "/api/v1/engine/advisory-config"
CACHE_KEY = "advisory_config"

__all__ = ["ADVISORY_CONFIG_PATH", "CACHE_KEY", "AdvisoryConfigClient", "ConditionalGet"]


class AdvisoryConfigClient(PulledDocument[AdvisoryConfig]):
    path = ADVISORY_CONFIG_PATH
    cache_key = CACHE_KEY
    name = "advisory config"
    model = AdvisoryConfig
