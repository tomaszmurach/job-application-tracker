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
    with op.batch_alter_table(
        "applications",
        schema=None,
        recreate="always",
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "applied_at",
                sa.DateTime(),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table(
        "applications",
        schema=None,
        recreate="always",
    ) as batch_op:
        batch_op.drop_column("applied_at")
