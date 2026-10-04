"""rev4 engine scoped replicas (TAA-709, PLAN §A32)

Every replicated table gains ``engine_id``. Tables with a natural or engine-chosen key get it as the first
primary-key column; tables with a local autoincrement id get an indexed column, and those without a natural
key also get ``source_id`` (the engine's own id), unique per engine. The idempotency keys of order and paper
intents and the suitability hour key become unique per engine.

Backfill: in a cloud database, the rows replicated before this revision came from the one engine allowed so
far; they are assigned to the registered engine seen most recently (audit events to the engine named in
their chain). An engine database has no registered engines and keeps ``local``.

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-04 18:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0020'
down_revision: str | None = '0019'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# table -> primary-key columns before this revision
KEYED: dict[str, list[str]] = {
    'decision_records': ['decision_id'],
    'order_intents': ['intent_id'],
    'paper_accounts': ['account_key'],
    'paper_intents': ['intent_id'],
    'paper_positions': ['ticket'],
    'risk_baselines': ['account_key', 'period', 'period_key'],
    'risk_state': ['account_key'],
    'risk_deals': ['account_key', 'ticket'],
    'breaker_states': ['name', 'scope_key'],
    'runs': ['run_id'],
    'config_snapshots': ['config_hash'],
    'symbol_catalog': ['server', 'symbol'],
    'opportunities': ['opportunity_id'],
    'shadow_trades': ['shadow_id'],
    'calibration_tables': ['version'],
}
TAGGED = [
    'audit_events',
    'decision_checks',
    'breaker_events',
    'kill_switch_events',
    'suitability_snapshots',
    'evidence_model_versions',
]
SOURCED = ['breaker_events', 'kill_switch_events', 'evidence_model_versions']
IDEMPOTENT = ['order_intents', 'paper_intents']


def _engine_id() -> sa.Column:
    return sa.Column('engine_id', sa.String(length=64), server_default='local', nullable=False)


def upgrade() -> None:
    for table, pk in KEYED.items():
        with op.batch_alter_table(table) as batch_op:  # SQLite recreates; Postgres alters in place
            batch_op.add_column(_engine_id())
            batch_op.drop_constraint(f'pk_{table}', type_='primary')
            batch_op.create_primary_key(f'pk_{table}', ['engine_id', *pk])
            if table in IDEMPOTENT:
                batch_op.drop_constraint(f'uq_{table}_idempotency_key', type_='unique')
                batch_op.create_unique_constraint(f'uq_{table}_engine_id', ['engine_id', 'idempotency_key'])
    for table in TAGGED:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(_engine_id())
            batch_op.create_index(f'ix_{table}_engine_id', ['engine_id'], unique=False)
            if table in SOURCED:
                batch_op.add_column(sa.Column('source_id', sa.BigInteger(), nullable=True))
                batch_op.create_unique_constraint(f'uq_{table}_engine_id', ['engine_id', 'source_id'])
            if table == 'suitability_snapshots':
                batch_op.drop_constraint('uq_suitability_symbol_hour', type_='unique')
                batch_op.create_unique_constraint(
                    'uq_suitability_symbol_hour', ['engine_id', 'server', 'symbol', 'hour']
                )
    _backfill()


def _backfill() -> None:
    conn = op.get_bind()
    owner = conn.execute(
        sa.text(
            'SELECT engine_id FROM engines '
            'ORDER BY CASE WHEN last_seen_at IS NULL THEN 1 ELSE 0 END, last_seen_at DESC, created_at DESC'
        )
    ).first()
    if owner is None:  # an engine database, or a cloud without engines: nothing was replicated
        return
    for table in [*KEYED, *TAGGED]:
        if table == 'audit_events':
            continue
        conn.execute(sa.update(sa.table(table, sa.column('engine_id'))).values(engine_id=owner[0]))
    conn.execute(
        sa.text("UPDATE audit_events SET engine_id = substr(chain, 8) WHERE chain LIKE 'engine:%'")
    )


def downgrade() -> None:
    # Only possible while the replicas hold one engine's rows (the old keys are not engine-scoped).
    for table in TAGGED:
        with op.batch_alter_table(table) as batch_op:
            if table == 'suitability_snapshots':
                batch_op.drop_constraint('uq_suitability_symbol_hour', type_='unique')
                batch_op.create_unique_constraint('uq_suitability_symbol_hour', ['server', 'symbol', 'hour'])
            if table in SOURCED:
                batch_op.drop_constraint(f'uq_{table}_engine_id', type_='unique')
                batch_op.drop_column('source_id')
            batch_op.drop_index(f'ix_{table}_engine_id')
            batch_op.drop_column('engine_id')
    for table, pk in KEYED.items():
        with op.batch_alter_table(table) as batch_op:  # SQLite recreates; Postgres alters in place
            if table in IDEMPOTENT:
                batch_op.drop_constraint(f'uq_{table}_engine_id', type_='unique')
                batch_op.create_unique_constraint(f'uq_{table}_idempotency_key', ['idempotency_key'])
            batch_op.drop_constraint(f'pk_{table}', type_='primary')
            batch_op.create_primary_key(f'pk_{table}', pk)
            batch_op.drop_column('engine_id')
