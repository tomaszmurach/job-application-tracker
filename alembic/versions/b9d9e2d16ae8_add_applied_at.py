"""add applied_at

Revision ID: b9d9e2d16ae8
Revises: cdd629732d9d
Create Date: 2026-09-16 14:10:41.056585

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9d9e2d16ae8'
down_revision: Union[str, Sequence[str], None] = 'cdd629732d9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    column = sa.Column(
        "applied_at",
        sa.DateTime(),
        server_default=sa.text("(CURRENT_TIMESTAMP)"),
        nullable=False,
    )
    if op.get_bind().dialect.name == "sqlite":
        # SQLite needs table recreation to add a column with this default.
        with op.batch_alter_table("applications", recreate="always") as batch_op:
            batch_op.add_column(column)
    else:
        # Native ALTER preserves PostgreSQL's existing table and ID sequence.
        op.add_column("applications", column)


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("applications", recreate="always") as batch_op:
            batch_op.drop_column("applied_at")
    else:
        op.drop_column("applications", "applied_at")
