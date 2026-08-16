"""Add league draft state columns

Revision ID: a7c3e91f4b2d
Revises: 10ca8b1425c4
Create Date: 2026-08-15 19:58:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a7c3e91f4b2d"
down_revision: Union[str, None] = "10ca8b1425c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leagues",
        sa.Column("status", sa.String(length=16), server_default="setup", nullable=False),
    )
    op.add_column(
        "leagues",
        sa.Column("roster_size", sa.SmallInteger(), server_default="8", nullable=False),
    )
    op.add_column(
        "leagues",
        sa.Column("draft_order", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("leagues", "draft_order")
    op.drop_column("leagues", "roster_size")
    op.drop_column("leagues", "status")
