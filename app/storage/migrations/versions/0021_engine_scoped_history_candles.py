"""engine scoped history candles (TAA-706)

``history_candles`` gains ``engine_id`` as the first primary-key column, like the replicated tables of
revision 0020: the cloud keeps each engine's uploaded and streamed bars apart. Existing rows keep ``local``
(they were written by a local tool, not by an engine through ingest).

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-04 19:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0021'
down_revision: str | None = '0020'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PK = ['server', 'symbol', 'timeframe', 'open_time']


def upgrade() -> None:
    with op.batch_alter_table('history_candles') as batch_op:  # SQLite recreates; Postgres alters in place
        batch_op.add_column(sa.Column('engine_id', sa.String(length=64), server_default='local', nullable=False))
        batch_op.drop_constraint('pk_history_candles', type_='primary')
        batch_op.create_primary_key('pk_history_candles', ['engine_id', *PK])


def downgrade() -> None:
    # Only possible while the table holds one engine's bars.
    with op.batch_alter_table('history_candles') as batch_op:
        batch_op.drop_constraint('pk_history_candles', type_='primary')
        batch_op.create_primary_key('pk_history_candles', PK)
        batch_op.drop_column('engine_id')
