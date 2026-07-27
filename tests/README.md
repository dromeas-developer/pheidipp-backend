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
