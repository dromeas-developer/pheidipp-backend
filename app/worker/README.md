# app/worker/

## Purpose
Procrastinate worker application — PostgreSQL-backed async task queue for heavy processing. Tasks defined here are enqueued by the API layer (via FastAPI route handlers) and executed by a separate worker process. This keeps API responses fast by deferring FIT parsing, twin recalibration, and post-workout analysis to the background.

## Contents
### Worker
| File | Responsibility |
|---|---|
| `app.py` | Procrastinate `App` instance with `Psycopg2Connector` and registered async tasks: `fit_ingest`, `post_workout_task`, `signal_cleaning_task`, `threshold_detection_task` |

## Architecture Notes
- Procrastinate 2.x is used deliberately with `Psycopg2Connector` for psycopg2 compatibility; the queue is transitional and 3.x migration is intentionally deferred.
- The worker reads `PROCRASTINATE_DATABASE_URL` from environment — the DSN converter in `app.config` strips SQLAlchemy `+driver` suffixes for procrastinate compatibility.
- Workers are started via `procrastinate --app=app.worker.app worker` as a separate process from the API server.
- All tasks are `async def` and create their own `AsyncSession` instances — no session sharing between tasks or with the API layer.
- Task queue invariants per `async-pipeline.md`: API responses never wait for heavy processing; queue backend is decoupled from the API.

## Cross-References
- [Platform: Async Pipeline](../../docs/architecture/04-platform/async-pipeline.md) — task queue invariants and worker topology
