"""ORM models. Import everything here so Alembic autogenerate sees the full metadata."""

from app.storage.models.advisory import (
    CalibrationTableRow,
    EvidenceModelVersionRow,
    OpportunityRow,
    ShadowTradeRow,
    SuitabilitySnapshotRow,
    SymbolCatalogRow,
)
from app.storage.models.backtests import BacktestRunRow
from app.storage.models.base import Base, utcnow
from app.storage.models.decisions import DecisionCheckRow, DecisionRecordRow
from app.storage.models.execution import OrderIntentRow
from app.storage.models.market import HistoryCandle, ProcessedCandle
from app.storage.models.notifications import NotificationPrefsRow, NotificationRow, PushSubscriptionRow
from app.storage.models.paper import PaperAccountRow, PaperIntentRow, PaperPositionRow
from app.storage.models.risk import BreakerEventRow, BreakerStateRow, RiskBaseline, RiskDeal, RiskState
from app.storage.models.sync import (
    AuditReplicaRow,
    CommandLogRow,
    EngineCommandRow,
    EngineHeartbeatRow,
    IngestNonceRow,
    OutboxEventRow,
    ReplicaVersionRow,
    StreamEventRow,
    StreamHeadRow,
)
from app.storage.models.system import (
    AuditChainHead,
    AuditEvent,
    ConfigSnapshot,
    EngineState,
    KillSwitchEvent,
    Run,
)
from app.storage.models.web import EngineRow, LoginThrottleRow, SessionRow, UserAdvisoryPrefsRow, UserRow
from app.storage.models.worker import WorkerHeartbeatRow, WorkerJobRow, WorkerScheduleRow

__all__ = [
    "AuditChainHead",
    "AuditEvent",
    "AuditReplicaRow",
    "BacktestRunRow",
    "Base",
    "BreakerEventRow",
    "BreakerStateRow",
    "CalibrationTableRow",
    "CommandLogRow",
    "ConfigSnapshot",
    "DecisionCheckRow",
    "DecisionRecordRow",
    "EngineCommandRow",
    "EngineHeartbeatRow",
    "EngineRow",
    "EngineState",
    "EvidenceModelVersionRow",
    "HistoryCandle",
    "IngestNonceRow",
    "KillSwitchEvent",
    "LoginThrottleRow",
    "NotificationPrefsRow",
    "NotificationRow",
    "OpportunityRow",
    "OrderIntentRow",
    "OutboxEventRow",
    "PaperAccountRow",
    "PaperIntentRow",
    "PaperPositionRow",
    "ProcessedCandle",
    "PushSubscriptionRow",
    "ReplicaVersionRow",
    "RiskBaseline",
    "RiskDeal",
    "RiskState",
    "Run",
    "SessionRow",
    "ShadowTradeRow",
    "StreamEventRow",
    "StreamHeadRow",
    "SuitabilitySnapshotRow",
    "SymbolCatalogRow",
    "UserAdvisoryPrefsRow",
    "UserRow",
    "WorkerHeartbeatRow",
    "WorkerJobRow",
    "WorkerScheduleRow",
    "utcnow",
]
