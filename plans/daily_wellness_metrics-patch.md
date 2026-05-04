# Daily Wellness Metrics for Athletes - Implementation Plan

## Models
1. Fix AthleteWellness model - add id and relationship
   - Objective: Add UUID primary key and fix relationship
   - File: `app/models/wellness.py` [MODIFY]
   - Actions:
     - Add `id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))` as first field
     - Change `athlete_id` from primary_key=True to nullable=False with just ForeignKey
     - Change `metric_date` from primary_key=True to nullable=False
     - Add `__table_args__` with UniqueConstraint on (athlete_id, metric_date)

2. Add wellness_metrics relationship to Athlete model
   - Objective: Add back-reference relationship
   - File: `app/models/athlete.py` [MODIFY]
   - Actions:
     - Add `wellness_metrics: Mapped[list["AthleteWellness"]] = relationship(back_populates="athlete")`

3. Create corrective Alembic migration to update AthleteWellness hypertable
   - Objective: Create correct table with id, unique constraint, hypertable
   - File: `migrations/versions/add_athlete_wellness_table.py` [CREATE]
   - Actions:
     - Execute `CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;`
     - Execute `CREATE EXTENSION IF NOT EXISTS vector;`
     - Create `athlete_wellness` table  with all columns defined in the model
     - Add index on athlete_id
     - Add unique constraint on (athlete_id, metric_date)
     - Execute `SELECT create_hypertable('athlete_wellness', 'metric_date', if_not_exists => TRUE);`