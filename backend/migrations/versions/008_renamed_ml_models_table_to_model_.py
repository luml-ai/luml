"""Renamed ml_models table to model_artifacts

Revision ID: 008
Revises: 007
Create Date: 2025-07-31 19:39:57.540538

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '008'
down_revision: str | None = '007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute('ALTER TABLE ml_models RENAME TO model_artifacts')


def downgrade() -> None:
    op.execute('ALTER TABLE model_artifacts RENAME TO ml_models')
