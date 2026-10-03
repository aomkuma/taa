"""Opportunity statuses (PLAN §A26), shared by the engine's lifecycle and the cloud personalizer."""

from __future__ import annotations

from enum import StrEnum


class OpportunityStatus(StrEnum):
    CANDIDATE = "CANDIDATE"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"
    FOLLOWED = "FOLLOWED"


OPEN = (OpportunityStatus.CANDIDATE.value, OpportunityStatus.ACTIVE.value)
