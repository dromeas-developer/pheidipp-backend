# Session Count Computation

## Purpose

- Deterministic Python function that computes the number of sessions for a given week
- Inputs: `AdjustedWeeklyIntent.target_session_count` (coach's hint) + `target_distribution` (continuous) + availability constraints
- Output: integer session count
- This is pure Python — no LLM reasoning required
- The coach decides the load; availability is a constraint

---

## Input Type

```python
@dataclass
class SessionCountInput:
    target_session_count: int   # from WeeklyDistribution or PhaseDescriptor (coach's hint)
    target_distribution: dict   # from AdjustedWeeklyIntent.target_distribution (continuous)
    max_available: int          # derived from AthletePreferences.weekly_schedule at runtime
    max_sessions: int | None    # from AdjustedWeeklyIntent (pre-week review override)
    is_recovery_week: bool      # from WeeklyDistribution.is_recovery_week
```

---

## Helper: Derive Max Available Sessions

```python
def derive_max_available(weekly_schedule: WeeklySchedule) -> int:
    """Count available days in the weekly schedule.

    Called at runtime by PreWeekReviewService — no stored field needed.
    """
    days = [
        weekly_schedule.monday,
        weekly_schedule.tuesday,
        weekly_schedule.wednesday,
        weekly_schedule.thursday,
        weekly_schedule.friday,
        weekly_schedule.saturday,
        weekly_schedule.sunday,
    ]
    return sum(1 for day in days if day.available)
```

---

## Computation

```python
def compute_session_count(input: SessionCountInput) -> int:
    """Compute session count for a week.

    Resolution order:
    1. Start with plan target (coach's hint from weekly distribution)
    2. Adjust based on intensity profile (high aerobic → more sessions, threshold → fewer)
    3. Cap at max available sessions (derived from weekly_schedule)
    4. Override with max_sessions if pre-week review set it
    """
    # Start with plan target
    base_count = input.target_session_count

    # Adjust based on target_distribution intensity profile
    # High aerobic emphasis → maintain or increase session count
    # High threshold/vo2max emphasis → cap to ensure recovery
    # Floor of 3 for easy weeks = coach's preferred minimum before availability capping.
    # Availability (max_available) may reduce further — that's the hard constraint.
    dist = input.target_distribution
    intensity_load = dist.threshold + dist.vo2max + dist.neuromuscular
    
    if intensity_load > 0.3:
        # High-intensity heavy week → cap to ensure recovery
        computed = min(5, base_count)
    elif dist.low_aerobic > 0.7:
        # Easy/aerobic dominant week → can sustain higher volume
        computed = max(3, base_count)
    else:
        # Balanced week → use plan target as-is
        computed = base_count

    # Cap at max available sessions (derived from weekly_schedule)
    computed = min(computed, input.max_available)

    # Override if schedule-constrained (pre-week review)
    if input.max_sessions is not None and input.max_sessions < computed:
        return input.max_sessions

    return computed
```

---

## Invariants

- Session count is always ≥ 1 (even under maximum reduction)
- Plan target is the coach's intent; availability is the athlete's constraint
- Floor of 3 on easy weeks is the coach's preferred minimum; availability may reduce further
- `max_sessions` is the pre-week review's explicit override (emergency brake)
- This function is deterministic: same inputs always produce the same output

---

## How It Feeds the Weekly Synthesis Agent

The weekly synthesis agent receives `session_count` as a pre-computed input, not as something it computes. The flow:

1. `PreWeekReviewService` (or `PlanGenerationService` for week 1) evaluates conditions
2. `derive_max_available()` counts available days from `AthletePreferences.weekly_schedule`
3. `compute_session_count()` runs with plan target, target distribution, availability, and any override
4. `AdjustedWeeklyIntent` includes `session_count` as a field
5. `WeeklySynthesisAgent` receives `AdjustedWeeklyIntent` and distributes sessions across available days

The agent does not recompute session count — it trusts the pre-computed value.

---

## Cross-References

- Pre-week review: `03-agents/pre-week-review-agent.md`
- Weekly synthesis: `03-agents/weekly-synthesis-agent.md`
- AdjustedWeeklyIntent: `03-agents/pre-week-review-agent.md` → Output Contract
- AthletePreferences: `01-entities/athlete-preferences.md`
