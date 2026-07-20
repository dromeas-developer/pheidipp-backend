> **Baseline — migrated from** `docs/implementation/phase-1/phase-consistency-p1-fix-patterns-and-documentation.md` **on** 2026-07-19.
> This plan documents what was built in Phase 1-8, verified against the current codebase on 2026-07-19.

## Batch Objective

Cross-cutting cleanup pass after Phase 1 completion: extract shared email normalization utility, add explanatory comments to the async ingestion pipeline, and clarify event firing timing documentation to resolve an apparent `[after_commit]` vs `[uncommitted]` labelling inconsistency.

## Preconditions

All Phase 1 sub-phases complete. Depends on: `AuthService`, `AthleteRepository`, `AthleteAuthRepository`, `ActivityIngestionService`, `04-platform/event-topology.md`.

## Scope

- **Event-topology documentation**: Add "Event Firing Timing Clarification" section to `event-topology.md` explaining that `[after_commit]` (service commits its own transaction) and `[uncommitted]` (worker/agent returns without committing; caller commits) both follow the same transactional outbox pattern
- **Email normalization utility**: Create `app/utils/email_utils.py` with `normalize_email(email: str) -> str` (lowercase + strip); refactor `AuthService`, `AthleteRepository`, and `AthleteAuthRepository` to use it instead of inline `.lower().strip()`
- **Explanatory comments**: Add comments in `ActivityIngestionService.ingest()` and `ingest_async()` explaining why events fire within the transaction (outbox pattern)

## Steps

1. [OWNER: Coder] Add "Event Firing Timing Clarification" section to `docs/architecture/04-platform/event-topology.md`. Explain that `[after_commit]` labels apply when the service commits, `[uncommitted]` labels apply when the caller (worker) commits — both follow the transactional outbox pattern.

2. [OWNER: Coder] Create `app/utils/email_utils.py` with `normalize_email(email: str) -> str` — lowercase and strip. This is the canonical normalization point.

3. [OWNER: Coder] Refactor `AuthService` to remove `_normalize_email` static method and use `normalize_email` from `app.utils.email_utils`.

4. [OWNER: Coder] Refactor `AthleteRepository.get_by_normalized_email` and `email_exists` to use `normalize_email`.

5. [OWNER: Coder] Refactor `AthleteAuthRepository.get_email_auth_by_normalized_email` to use `normalize_email` if input normalization is needed.

6. [OWNER: Coder] Add explanatory comment in `ActivityIngestionService.ingest()` before the event publication — reference the transactional outbox pattern and event-topology.md.

7. [OWNER: Coder] Add explanatory comment in `ActivityIngestionService.ingest_async()` before the event publication.

## Context Needed

- `docs/architecture/04-platform/event-topology.md` (existing event flow documentation)
- `app/services/auth_service.py` (existing `_normalize_email` static method)
- `app/repositories/athlete_repository.py` (existing inline normalization)
- `app/repositories/athlete_auth_repository.py` (existing inline normalization)
- `app/services/activity_ingestion_service.py` (event publication call sites)

## Batch Success Criteria

- `app/utils/email_utils.py` exists with `normalize_email` function
- `AuthService._normalize_email` removed; uses shared utility
- `AthleteRepository` uses shared utility in both `get_by_normalized_email` and `email_exists`
- `AthleteAuthRepository` uses shared utility
- `event-topology.md` has "Event Firing Timing Clarification" section
- `ActivityIngestionService.ingest()` and `ingest_async()` have explanatory comments referencing the outbox pattern
- All existing tests pass — behavioral equivalence preserved

## Files Expected To Change

- `app/utils/email_utils.py` — new utility module
- `app/services/auth_service.py` — remove inline normalization, import shared utility
- `app/repositories/athlete_repository.py` — use shared utility
- `app/repositories/athlete_auth_repository.py` — use shared utility
- `app/services/activity_ingestion_service.py` — add comments
- `docs/architecture/04-platform/event-topology.md` — add timing clarification section

## Coder Notes

- No schema changes, no migrations, no new events.
- `email_utils` is imported by full path (`from app.utils.email_utils import normalize_email`) — the `__init__.py` is intentionally empty.
- The `[after_commit]` / `[uncommitted]` labels exist only in documentation, not as source-code annotations. This is by design.
- Verified against current codebase (2026-07-19): utility exists, all consumers refactored, documentation updated. No discrepancies.
