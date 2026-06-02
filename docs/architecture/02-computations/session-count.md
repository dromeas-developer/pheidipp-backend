# Session Count Computation

## Purpose

- Deterministic Python function that computes the number of sessions for a given week
- Inputs: `AdjustedWeeklyIntent` (or `PhaseArcEntry` for week 1) + `AthletePreferences`
- Output: integer session count
- This is pure Python — no LLM reasoning required

---

## Input Type

```python
@dataclass
class SessionCountInput:
    intensity_bias: str  # 'easy' | 'balanced' | 'moderate' | 'quality'
    max_sessions: int | None  # schedule-constrained override from pre-week review
    weekly_session_count: int  # athlete preference
```

---

## Computation

```python
def compute_session_count(input: SessionCountInput) -> int:
    """Compute session count for a week.

    Rules:
    - 'easy' weeks: reduce by 1, floor of 3
    - 'balanced' weeks: use athlete preference
    - 'moderate' weeks: use athlete preference
    - 'quality' weeks: cap at 5
    - Schedule-constrained override: use lower of computed and max_sessions
    """
    base_count = input.weekly_session_count

    # Adjust based on intensity bias
    match input.intensity_bias:
        case "easy":
            computed = max(3, base_count - 1)
        case "balanced":
            computed = base_count
        case "moderate":
            computed = base_count
        case "quality":
            computed = min(5, base_count)
        case _:
            computed = base_count

    # Override if schedule-constrained
    if input.max_sessions is not None and input.max_sessions < computed:
        return input.max_sessions

    return computed
```

---

## Invariants

- Session count is always ≥ 1 (even under maximum reduction)
- Session count respects both adjusted intent and athlete preference — the lower of the two wins when they conflict
- This function is deterministic: same inputs always produce the same output

---

## How It Feeds the Weekly Synthesis Agent

The weekly synthesis agent receives `session_count` as a pre-computed input, not as something it computes. The flow:

1. `PreWeekReviewService` (or `PlanGenerationService` for week 1) evaluates conditions
2. `compute_session_count()` runs as part of the review output
3. `AdjustedWeeklyIntent` includes `session_count` as a field
4. `WeeklySynthesisAgent` receives `AdjustedWeeklyIntent` and distributes sessions across available days

The agent does not recompute session count — it trusts the pre-computed value.

---

## Cross-References

- Pre-week review: `03-agents/pre-week-review-agent.md`
- Weekly synthesis: `03-agents/weekly-synthesis-agent.md`
- AdjustedWeeklyIntent: `03-agents/pre-week-review-agent.md` → Output Contract
- AthletePreferences: `01-entities/athlete-preferences.md`
