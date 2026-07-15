"""Backfill deployment monitoring_mode from satellite_parameters.monitoring_enabled

Unifies the two monitoring flags onto ``deployments.monitoring_mode``: deployments
previously toggled via ``satellite_parameters['monitoring_enabled'] = true`` are set to
``full`` so the satellite (which now reads ``monitoring_mode``) keeps recording events.

Revision ID: 035
Revises: 034
Create Date: 2026-07-08 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "035"
down_revision: str | None = "034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE deployments
        SET monitoring_mode = 'full'
        WHERE monitoring_mode = 'off'
          AND satellite_parameters->>'monitoring_enabled' = 'true'
        """
    )


def downgrade() -> None:
    # Best-effort inverse: revert only rows still enabled in satellite_parameters.
    op.execute(
        """
        UPDATE deployments
        SET monitoring_mode = 'off'
        WHERE monitoring_mode = 'full'
          AND satellite_parameters->>'monitoring_enabled' = 'true'
        """
    )
