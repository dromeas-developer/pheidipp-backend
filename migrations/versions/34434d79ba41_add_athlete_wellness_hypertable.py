"""add_athlete_wellness_hypertable

Revision ID: 34434d79ba41
Revises: 29c40204bcec
Create Date: 2026-05-03 17:18:44.519766

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '34434d79ba41'
down_revision: Union[str, None] = '29c40204bcec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.create_table('athlete_wellness',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('athlete_id', sa.UUID(), nullable=False),
    sa.Column('metric_date', sa.Date(), nullable=False),
    sa.Column('sleep_total', sa.Integer(), nullable=True),
    sa.Column('sleep_light', sa.Integer(), nullable=True),
    sa.Column('sleep_deep', sa.Integer(), nullable=True),
    sa.Column('sleep_rem', sa.Integer(), nullable=True),
    sa.Column('sleep_awake', sa.Integer(), nullable=True),
    sa.Column('resting_hr', sa.Integer(), nullable=True),
    sa.Column('hrv', sa.Integer(), nullable=True),
    sa.Column('weight', sa.Float(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('timezone', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('athlete_id', 'metric_date', name='uq_athlete_wellness_date')
    )
    op.create_index(op.f('ix_athlete_wellness_athlete_id'), 'athlete_wellness', ['athlete_id'], unique=False)
    op.execute("SELECT create_hypertable('athlete_wellness', 'metric_date', if_not_exists => TRUE);")
    # ### end Alembic commands ###


def downgrade() -> None:
    op.execute("SELECT drop_hypertable('athlete_wellness', if_exists => TRUE, cascade => TRUE);")
    op.drop_index(op.f('ix_athlete_wellness_athlete_id'), table_name='athlete_wellness')
    op.drop_table('athlete_wellness')
    # ### end Alembic commands ###
