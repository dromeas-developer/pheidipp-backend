# Implementation Plan: Consistency-Phase-1 — Fix Identified Inconsistencies and Tech Debt

## Plan ID: Consistency-Phase-1-P1

## Sub-Phase Reference
Sub-Phase ID: Consistency-Phase-1
Sub-Phase Title: Fix Phase-1 Inconsistencies and Technical Debt

## Objective
Address findings from the Phase-1 consistency validation report. The report identified two coder-level fixes (email normalization extraction and explanatory comments) and one major finding requiring architectural clarification (event-firing timing pattern). This plan executes the coder fixes and documents the architectural clarification to prevent future confusion.

## Scope
- **Architectural Clarification**: Update event-topology documentation to explicitly describe when each event-firing label applies (after_commit vs uncommitted), confirming both follow the transactional outbox pattern
- **Email Normalization Extraction**: Create `app/utils/email_utils.py` with `normalize_email()` function and refactor 3 locations to use it
- **Explanatory Comments**: Add clarifying comments to `activity_ingestion_service.py` explaining why events fire within the worker transaction in the async pipeline path

## Out Of Scope
- Any changes to event publishing semantics or transaction boundaries
- Refactoring of the seven `get_by_athlete_id` repository boilerplate
- Splitting `ContextBudgetService` or `PlanGenerationService` (observations, not action items)
- Changes to error class naming or structure
- Introduction of new entities or events

## Architecture Contracts
- `04-platform/event-topology.md` — DOCUMENTS (clarifies existing pattern, no semantic change)
- `04-platform/system-event.md` — DEPENDS ON (transactional outbox pattern already defined)
- Event Publisher existing semantics — DEPENDS ON (no change to EventPublisher.publish())

## Invariants
- Transactional outbox pattern is preserved: events are written to outbox in the same transaction as domain state, external publication occurs after commit
- Email normalization produces identical output (lowercase, stripped) — behavioral equivalence required
- All existing imports in `app/services/__init__.py` continue to work after extraction

## Implementation Steps

1. [OWNER: Coder] **Update event-topology.md with explicit timing clarification**

   Add a new section "Event Firing Timing Clarification" to `docs/architecture/04-platform/event-topology.md` explaining:
   - Both synchronous services (AuthService, OnboardingService, PlanGenerationService) and asynchronous workers (ActivityIngestionService via procrastinate, FirstMessageAgent, WorkoutGenerationAgent, PostWorkoutAgent) follow the same transactional outbox pattern
   - The `[after_commit]` label applies when the service commits its own transaction and external publishers fire the event afterward
   - The `[uncommitted]` label applies when the service writes to the outbox as part of its transaction, and the external publisher (a separate process) fires the event after that transaction commits
   - Both patterns ensure consumers never see state that wasn't committed — the apparent inconsistency is a labeling artifact, not an architectural violation
   - Reference ADR-004 if it exists regarding transactional outbox semantics

2. [OWNER: Coder] **Create shared email normalization utility**

   Create `app/utils/email_utils.py` with:
   ```python
   def normalize_email(email: str) -> str:
       """Normalize email to lowercase and strip leading/trailing whitespace.

       Call this before any email persistence or lookup to ensure
       case-insensitive matching. The database enforces uniqueness via
       a lower(email) index on the athletes table.
       """
       return email.strip().lower()
   ```

   Add directory to `app/utils/__init__.py` if not present, or create the module.

3. [OWNER: Coder] **Refactor AuthService to use shared utility**

   In `app/services/auth_service.py`:
   - Remove the static method `_normalize_email` (around line 458)
   - Import `normalize_email` from `app.utils.email_utils`
   - Replace all `self._normalize_email(...)` calls with `normalize_email(...)`
   - Update the import list at the top of the file

4. [OWNER: Coder] **Refactor AthleteRepository to use shared utility**

   In `app/repositories/athlete_repository.py`:
   - In the `get_by_normalized_email` method (around line 27), replace the inline `.lower().strip()` with a call to `normalize_email()`
   - Import `normalize_email` from `app.utils.email_utils`
   - The method signature remains unchanged — normalization happens on input

5. [OWNER: Coder] **Refactor AthleteAuthRepository to use shared utility**

   In `app/repositories/athlete_auth_repository.py`:
   - In the `get_email_auth_by_normalized_email` method (around line 34), verify if the input is already normalized or if normalization is needed
   - If normalization is needed, import and use `normalize_email`
   - Ensure the join query uses the normalized form consistently

6. [OWNER: Coder] **Add explanatory comment to ActivityIngestionService.ingest()**

   In `app/services/activity_ingestion_service.py`, add a comment before the `activity_ingested` event publication in the `ingest()` method (around line 358):
   ```python
   # Publish event within the current transaction. The EventPublisher
   # writes to the outbox tables (system_events + system_event_outbox);
   # the external publisher worker reads from the outbox after this
   # transaction commits. This follows the same transactional outbox
   # pattern as sync services — see docs/architecture/04-platform/event-topology.md
   ```

7. [OWNER: Coder] **Add explanatory comment to ActivityIngestionService.ingest_async()**

   In `app/services/activity_ingestion_service.py`, add a comment before the `activity_ingested` event publication in the `ingest_async()` method (around line 436):
   ```python
   # Publish event within the worker's transaction. The worker commits
   # after this method returns; the external publisher reads from the
   # outbox post-commit. Same transactional outbox pattern as sync
   # services — see docs/architecture/04-platform/event-topology.md
   ```

8. [OWNER: DevOps] **Review and apply any generated migrations**

   No schema changes are required for this sub-phase. Verify that no unintended migrations are generated.

9. [OWNER: Test Architect] **Verify tests pass after refactoring**

   Run the existing test suite to confirm:
   - Email normalization produces identical results (no behavioral change)
   - All service and repository methods that accepted normalized email still work
   - AuthService register/login flows continue to work
   - No import errors in the refactored modules

## Event Contracts
- No events produced or consumed by this plan
- Documentation clarification only — no change to event semantics, payload, or timing

## Pseudocode
```
Email normalization extraction:
  Create app/utils/email_utils.py
    normalize_email(email: str) -> str:
      return email.strip().lower()

  In AuthService:
    remove _normalize_email static method
    replace self._normalize_email(email) → normalize_email(email)
    add import

  In AthleteRepository.get_by_normalized_email:
    replace normalized_email.lower().strip() → normalize_email(normalized_email)
    add import

  In AthleteAuthRepository.get_email_auth_by_normalized_email:
    verify input already normalized or apply normalize_email()
    add import if needed

Documentation update:
  In event-topology.md:
    Add section "Event Firing Timing Clarification"
    Explain both patterns follow transactional outbox
    Clarify [after_commit] vs [uncommitted] labels
    Link to ADR-004 and system-event.md

Comment additions:
  In activity_ingestion_service.py:
    Add comment at ingest() event publish
    Add comment at ingest_async() event publish
```

## Testing Requirements
- `test_auth_service` passes: AuthService register/login work with extracted normalization
- `test_activity_ingestion_service` passes: Both sync and async ingestion paths work
- Email matching behavior unchanged: test with various whitespace/case inputs produces same results as before
- All imports in `app/services/__init__.py` resolve correctly (no broken exports)
- No new migrations generated (verify by running `alembic check`)
- Documentation renders correctly (Markdown syntax valid)

## Coder Handoff Notes
```
## Coder Scope
Execute:  Steps 1, 2, 3, 4, 5, 6, 7  [OWNER: Coder] — documentation update, utility extraction, refactoring, and comment additions
Skip:     Step 8 (DevOps — migration review),
          Step 9 (Test Architect — test verification)
```

Key implementation considerations:
- **Email normalization extraction**: This is a pure refactoring — behavior must be identical. The current implementation uses `email.strip().lower()` everywhere, so extract exactly that sequence.
- **Import organization**: Ensure `app/utils/` is a proper Python package (has `__init__.py`). Add `normalize_email` to the appropriate `__init__.py` files for clean imports.
- **Documentation update**: The event-topology clarification does not change architecture — it only explains why both patterns exist and confirms they follow the same transactional outbox principle.
- **Comment placement**: Add comments immediately before the `await self.events.publish(...)` calls in both methods. Keep them concise and reference the canonical documentation.
- **No functional changes**: This plan does not alter event semantics, transaction boundaries, or business logic. Verify all changes are purely cosmetic/organizational.
- **Test before refactoring**: Run the test suite before starting to establish a baseline. This makes it easy to confirm the refactoring didn't introduce regressions.
- **Atomic commits**: Consider splitting into three commits: (1) documentation update, (2) email utility extraction, (3) comment additions. This makes each change independently reviewable.