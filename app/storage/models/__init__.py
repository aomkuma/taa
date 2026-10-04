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
from app.storage.models.notifications import (
    NotificationPrefsRow,
    NotificationRow,
    OpportunityAlertRow,
    PushSubscriptionRow,
)
from app.storage.models.paper import PaperAccountRow, PaperIntentRow, PaperPositionRow
from app.storage.models.plans import (
    BillingEventRow,
    EntitlementOverrideRow,
    PlanRow,
    SubscriptionRow,
    UsageCounterRow,
)
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
from app.storage.models.web import (
    AccountProfileRow,
    EngineRow,
    LoginThrottleRow,
    SessionRow,
    UserAdvisoryPrefsRow,
    UserRow,
)
from app.storage.models.worker import WorkerHeartbeatRow, WorkerJobRow, WorkerScheduleRow

__all__ = [
    "AccountProfileRow",
    "AuditChainHead",
    "AuditEvent",
    "AuditReplicaRow",
    "BacktestRunRow",
    "Base",
    "BillingEventRow",
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
    "EntitlementOverrideRow",
    "EvidenceModelVersionRow",
    "HistoryCandle",
    "IngestNonceRow",
    "KillSwitchEvent",
    "LoginThrottleRow",
    "NotificationPrefsRow",
    "NotificationRow",
    "OpportunityAlertRow",
    "OpportunityRow",
    "OrderIntentRow",
    "OutboxEventRow",
    "PaperAccountRow",
    "PaperIntentRow",
    "PaperPositionRow",
    "PlanRow",
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
    "SubscriptionRow",
    "SuitabilitySnapshotRow",
    "SymbolCatalogRow",
    "UsageCounterRow",
    "UserAdvisoryPrefsRow",
    "UserRow",
    "WorkerHeartbeatRow",
    "WorkerJobRow",
    "WorkerScheduleRow",
    "utcnow",
]
