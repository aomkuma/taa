"""Risk-profile pull client: the engine owner's trading-profile limits from the cloud (PLAN §A33; TAA-710).

``GET /api/v1/engine/risk-profile`` returns a :class:`app.risk.limits.RiskProfileDoc`, polled every
``sync.risk_profile_seconds`` by :class:`app.sync.pull.PulledDocument` (cache key ``risk_profile``). The
engine combines it with its local ``RiskConfig`` through ``effective_risk``, so the document can only lower
the local limits. Without one (``current`` is None) the engine uses the local ``advisory.preferences``
trading profile, never the bare ``RiskConfig`` cage.
"""

from __future__ import annotations

from app.risk.limits import RiskProfileDoc
from app.sync.pull import PulledDocument

RISK_PROFILE_PATH = "/api/v1/engine/risk-profile"
CACHE_KEY = "risk_profile"


class RiskProfileClient(PulledDocument[RiskProfileDoc]):
    path = RISK_PROFILE_PATH
    cache_key = CACHE_KEY
    name = "risk profile"
    model = RiskProfileDoc
