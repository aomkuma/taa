"""shadow entry modes

`shadow_trades`: entry-mode variants (TAA-L702): `variant` widened to 16 characters (`PULLBACK_WIDE`) and
`entry_window_end` (a PENDING limit not filled before it is MISSED).

Revision ID: 0043
Revises: 0042
Create Date: 2026-10-07 17:20:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.storage.types


revision: str = '0043'
down_revision: str | None = '0042'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('shadow_trades', schema=None) as batch_op:
        batch_op.alter_column('variant', existing_type=sa.String(length=8), type_=sa.String(length=16),
                              existing_nullable=False)
        batch_op.add_column(sa.Column('entry_window_end', app.storage.types.UTCDateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('shadow_trades', schema=None) as batch_op:
        batch_op.drop_column('entry_window_end')
        batch_op.alter_column('variant', existing_type=sa.String(length=16), type_=sa.String(length=8),
                              existing_nullable=False)
