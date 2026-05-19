"""fix_wellness_table_defaults

Revision ID: 7a2b1c3d4e5f
Revises: 34434d79ba41
Create Date: 2026-05-14 21:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a2b1c3d4e5f'
down_revision: Union[str, None] = '4420f93ca53a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fix 1: Add gen_random_uuid() default to id column (if not already set)
    op.execute(
        "ALTER TABLE athlete_wellness ALTER COLUMN id SET DEFAULT gen_random_uuid();"
    )
    # Fix 2: Add primary key constraint on (athlete_id, metric_date) if not exists
    # Use DO block to conditionally add PK only if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE table_name = 'athlete_wellness'
                AND constraint_type = 'PRIMARY KEY'
            ) THEN
                ALTER TABLE athlete_wellness ADD PRIMARY KEY (athlete_id, metric_date);
            END IF;
        END $$;
    """)
    # ### end Alembic commands ###


def downgrade() -> None:
    # Remove primary key constraint
    op.execute(
        "ALTER TABLE athlete_wellness DROP CONSTRAINT athlete_wellness_pkey;"
    )
    # Remove default from id column
    op.execute(
        "ALTER TABLE athlete_wellness ALTER COLUMN id DROP DEFAULT;"
    )
    # ### end Alembic commands ###