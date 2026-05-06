---
id: ADR-006
status: accepted
tags: [database, timescale, time-series]
supersedes: ~
superseded-by: ~
---

# ADR 006: TimescaleDB for Time-Series Data

## Rules
**Hypertable Requirement**: Any table storing daily or time-series samples MUST be a TimescaleDB hypertable.

**Standard Tables**: Tables that are **not** time-series (e.g., versioned records with date ranges) MUST remain standard PostgreSQL tables.

**Migration Pattern**: Hypertables MUST be created using the exact migration sequence:
1. Enable TimescaleDB and vector extensions.
2. Create the table.
3. Convert the table to a hypertable using `create_hypertable()`.

**Time Column**: Hypertables MUST specify a time column (e.g., `timestamp`, `metric_date`) for partitioning.

**No Manual Schema Changes**: Schema changes for hypertables MUST be applied via Alembic migrations only.

## Decision
Pheidipp uses TimescaleDB to store time-series data (e.g., activity samples, wellness metrics, fitness metrics). This decision ensures efficient storage, querying, and retention of time-series data while leveraging PostgreSQL's ecosystem.

## Rationale
- **Performance**: TimescaleDB optimizes time-series data storage and querying, reducing query latency for time-based aggregations.
- **Scalability**: Hypertables automatically partition data by time, enabling efficient scaling for large datasets.
- **PostgreSQL Compatibility**: TimescaleDB is a PostgreSQL extension, allowing seamless integration with existing tools and libraries.
- **Retention Policies**: TimescaleDB supports automated data retention policies for time-series data.
- **pgvector Integration**: Enables vector-based queries for time-series data (e.g., similarity searches).

## Alternatives Rejected
| Option | Why Rejected |
|--------|--------------|
| Standard PostgreSQL tables | Poor performance for time-series queries and storage inefficiency. |
| InfluxDB | Adds operational complexity and deviates from the PostgreSQL ecosystem. |
| Custom partitioning | Manual partitioning is error-prone and harder to maintain. |

## Tradeoffs
**Pro**:
- Optimized for time-series data storage and querying.
- Seamless integration with PostgreSQL and existing tools.
- Automated partitioning and retention policies.

**Con**:
- Adds complexity to migrations and schema management.
- Requires TimescaleDB-specific SQL for advanced features.
- Not all PostgreSQL tools fully support TimescaleDB features.

## Compliance
### Compliant
```sql
-- Migration sequence for creating a hypertable
op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
op.create_table(
    'activity_samples',
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('athlete_id', sa.Integer, sa.ForeignKey('athletes.id')),
    sa.Column('timestamp', sa.TIMESTAMP, nullable=False),
    sa.Column('heart_rate', sa.Integer),
    sa.Column('power', sa.Integer),
)
op.execute(
    "SELECT create_hypertable('activity_samples', 'timestamp', if_not_exists => TRUE);"
)
```

### Non-Compliant
```sql
-- Standard table for time-series data (violates hypertable requirement)
op.create_table(
    'activity_samples',
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('athlete_id', sa.Integer, sa.ForeignKey('athletes.id')),
    sa.Column('timestamp', sa.TIMESTAMP, nullable=False),
    sa.Column('heart_rate', sa.Integer),
)
```

## Cross-References
[ADR-005: Async-First Database Access](./005-async-first-database-access.md) — Async database access rules for TimescaleDB.
[stack-truth.md](../../stack-truth.md) — TimescaleDB hypertable rules and migration patterns.