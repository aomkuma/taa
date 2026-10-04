"""ORM models. Import everything here so Alembic autogenerate sees the full metadata."""

from app.storage.models.advisory import (
    CalibrationTableRow,
    EvidenceModelVersionRow,
    OpportunityRow,
    ShadowTradeRow,
    SuitabilitySnapshotRow,
    SymbolCatalogRow,
)
from app.storage.models.base import Base, utcnow
from app.storage.models.decisions import DecisionCheckRow, DecisionRecordRow
from app.storage.models.execution import OrderIntentRow
from app.storage.models.market import HistoryCandle, ProcessedCandle
from app.storage.models.paper import PaperAccountRow, PaperIntentRow, PaperPositionRow
from app.storage.models.risk import BreakerEventRow, BreakerStateRow, RiskBaseline, RiskDeal, RiskState
from app.storage.models.sync import CommandLogRow, EngineCommandRow, IngestNonceRow, OutboxEventRow
from app.storage.models.system import (
    AuditChainHead,
    AuditEvent,
    ConfigSnapshot,
    EngineState,
    KillSwitchEvent,
    Run,
)
from app.storage.models.web import LoginThrottleRow, SessionRow, UserRow

__all__ = [
    "AuditChainHead",
    "AuditEvent",
    "Base",
    "BreakerEventRow",
    "BreakerStateRow",
    "CalibrationTableRow",
    "CommandLogRow",
    "ConfigSnapshot",
    "DecisionCheckRow",
    "DecisionRecordRow",
    "EngineCommandRow",
    "EngineState",
    "EvidenceModelVersionRow",
    "HistoryCandle",
    "IngestNonceRow",
    "KillSwitchEvent",
    "LoginThrottleRow",
    "OpportunityRow",
    "OrderIntentRow",
    "OutboxEventRow",
    "PaperAccountRow",
    "PaperIntentRow",
    "PaperPositionRow",
    "ProcessedCandle",
    "RiskBaseline",
    "RiskDeal",
    "RiskState",
    "Run",
    "SessionRow",
    "ShadowTradeRow",
    "SuitabilitySnapshotRow",
    "SymbolCatalogRow",
    "UserRow",
    "utcnow",
]
