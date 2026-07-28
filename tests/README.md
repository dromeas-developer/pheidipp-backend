# Test Suite — Lessons & Conventions

Accumulated do/don't lessons from real DevOps-reported test failures.
Each entry is dated and cross-referenced from `tests/MOCKING_CONTRACT.md`
Known Anti-Patterns where applicable.

---

## 2026-07-26 — Use enum members, not string literals, for model constructor fields

**Symptom:** Tests pass during initial generation but break silently when enum
values are renamed or model validation tightens. String literals bypass
import-time checking and won't fail until the database rejects the value.

**Root cause:** Model columns typed with SAEnum (e.g., `PhaseLabel`, `SessionType`,
`PlannedSessionStatus`) were being assigned raw string literals (`"aerobic_base"`,
`"easy_run"`, `"scheduled"`) instead of enum members (`PhaseLabel.AEROBIC_BASE`,
`SessionType.EASY_RUN`, `PlannedSessionStatus.SCHEDULED`).

**Failed pattern:**
```python
session = PlannedSession(
    phase_label="aerobic_base",
    session_type="easy_run",
    status="scheduled",
    session_priority="primary",
)
```

**Correct pattern:**
```python
from app.models.enums import PhaseLabel, SessionType, PlannedSessionStatus, SessionPriority

session = PlannedSession(
    phase_label=PhaseLabel.AEROBIC_BASE,
    session_type=SessionType.EASY_RUN,
    status=PlannedSessionStatus.SCHEDULED,
    session_priority=SessionPriority.PRIMARY,
)
```

**Why:**
1. **Import-time safety** — if an enum value is removed, the test fails at
   collection, not at runtime with a cryptic PostgreSQL error.
2. **Refactoring resilience** — renaming an enum's Python member (without
   changing the string value) keeps the test working.
3. **Self-documenting** — the enum member name tells the reader the domain
   value without needing to mentally map a string literal.

**Exception:** When testing CHECK constraint violations with an intentionally
invalid value that is not a valid enum member, use a string literal. Example:
`recovery_modifier_level="purple"` — `"purple"` is not a valid
`RecoveryModifierLevel` member, so a string literal is the only way to
exercise the database CHECK constraint.

**Scope:** All model constructor calls in tests (unit, integration, api, behaviour).
Applies to every SAEnum-typed column except those with `server_default`.

**Enums (from `app/models/enums.py`):**
Import only the enums your test file actually uses. Full reference:
`ActivitySource`, `BlockPosition`, `CheckpointStatus`, `CheckpointType`,
`DataTier`, `GoalEventType`, `GoalType`, `GpsSource`, `HrSource`,
`InjurySeverity`, `MessageType`, `PhaseLabel`, `PhysiologicalIntent`,
`PlannedSessionStatus`, `PowerSource`, `PrimaryTrainingPlatform`,
`RecoveryModifierLevel`, `SessionPriority`, `SessionPurpose`, `SessionSlot`,
`SessionType`, `Sex`, `SportBackground`, `StepType`, `TrainingGoalStatus`,
`TrainingPlanStatus`, `TrainingTimeOfDay`, `TwinConfidenceLevel`,
`TwinTrigger`, `WeeklyPlanStatus`, `WellnessTrend`.

---

## 2026-07-27 — Don't monkeypatch to raise during async session operations

**Symptom:** `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't await_only() here`

**Root cause:** Monkeypatching `RepoClass.add` or `AsyncSession.flush` to call the
original method then raise corrupts SQLAlchemy's async greenlet context. The
original method performs `session.add()` → `session.flush()` → `session.refresh()`,
and calling it from within a monkeypatched method breaks the greenlet propagation
that SQLAlchemy's async session relies on.

**Also applies to:** Any monkeypatch on `AsyncSession.flush` — the async greenlet
context is still corrupted regardless of where the monkeypatch is applied.

**Failed pattern:**
```python
async def failing_add(self, physiology):
    await original_add(self, physiology)
    raise RuntimeError("simulated failure")

monkeypatch.setattr(AthletePhysiologyRepository, "add", failing_add)
```

**Correct pattern:** Pre-insert a conflicting row to trigger a natural
`IntegrityError` on a database unique constraint. SQLAlchemy handles
`IntegrityError` through its normal async machinery — no greenlet corruption.

**Critical subtlety:** When `IntegrityError` fires, SQLAlchemy moves the session
into a failed-transaction state that **clears all ORM object `__dict__` entries**.
Accessing `athlete.id` (even just reading the PK) on the cleared object triggers
a lazy load → `MissingGreenlet`. **Capture all PKs into plain UUID locals before
the `pytest.raises` block:**
```python
from sqlalchemy.exc import IntegrityError

athlete, profile = await make_athlete_with_profile(db_session)
athlete_id = athlete.id  # ← capture BEFORE pytest.raises
profile_id = profile.id  # ← capture BEFORE pytest.raises

db_session.add(_make_existing_preferences(athlete_id))
await db_session.flush()

with pytest.raises(IntegrityError):
    await service.complete_onboarding(athlete_id=athlete_id, ...)

await db_session.rollback()
db_session.expire_all()
# Use the captured UUIDs — NOT athlete.id or profile.id
refreshed = await db_session.get(Athlete, athlete_id)
```

**Why:** The `IntegrityError` is raised by the database during the normal
flush cycle. SQLAlchemy's async session handles it through the standard
greenlet context — no monkeypatching, no corrupted state. The session
enters an inactive state after the error, and `await db_session.rollback()`
resets it cleanly. But the ORM objects' `__dict__` is wiped — all attribute
access after the error must go through captured locals or fresh queries.

**Scope:** Any integration test that needs to simulate a mid-transaction
failure while exercising the real `AsyncSession`. Cross-referenced in
`tests/MOCKING_CONTRACT.md` Known Anti-Patterns.
