"""add abandoned intent status and submit abandoned event

Revision ID: a3c8f1b2d4e5
Revises: 5b1ef7924cea
Create Date: 2026-07-17 15:55:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a3c8f1b2d4e5'
down_revision: Union[str, Sequence[str], None] = '5b1ef7924cea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE intentstatus ADD VALUE IF NOT EXISTS 'ABANDONED'")
    op.execute("ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'SUBMIT_ABANDONED'")


def downgrade() -> None:
    pass
