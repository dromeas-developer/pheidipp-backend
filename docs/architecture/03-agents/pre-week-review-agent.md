# pre-week-review-agent

## Purpose

- Evaluates the plan's intent for the upcoming week against accumulated execution data and current athlete state
- Adjusts the intent deterministically if the plan's assumptions no longer match reality
- Acts as a strategic quality gate before the weekly synthesis agent commits to sessions
- This is a Python service, not an LLM agent — all decision logic is deterministic

---

## Input Contract

---

## Trigger

Runs weekly, before the weekly synthesis agent. Triggered by:
- Scheduled task (e.g., every Sunday evening)
- `week_completed` event for the next week

---

## Input Type

```typescript
type PreWeekReviewInput = {
  // What the plan says for this week
  phase_arc_entry: PhaseArcEntry      // from TrainingPlan.phase_arc
  
  // What actually happened
  prior_weeks_summary: PriorWeekSummary[]
  // - sessions completed vs planned
  // - accumulated fatigue delta
  // - adaptation observations (if any new adaptation windows completed)
  // - checkpoint results (if any completed this cycle)
  
  // Current athlete state
  twin_state: TwinState
  current_wellness: RecoveryModifierLevel  // GREEN/AMBER/RED
  cycle_phase: CyclePhase | null
  
  // Schedule context
  athlete_preferences: AthletePreferences  // availability, time constraints
  
  // Confidence context
  confidence_level: TwinConfidenceLevel
  adaptation_signature: AdaptationObservation[] | null
}
```

---

## Output Contract

```typescript
type AdjustedWeeklyIntent = {
  // What this week is about (may be unchanged from plan)
  phase_label: PhaseLabel
  methodology: MethodologyTraitVector
  physiological_emphasis: string      // "aerobic base consolidation"
  intensity_bias: 'easy' | 'balanced' | 'moderate' | 'quality'
  
  // Session count for this week (computed by PreWeekReviewService)
  session_count: number               // from compute_session_count(); weekly planner reads this
  
  // Adjustments from the review
  adjustment_made: boolean
  adjustment_reason: string | null    // "athlete recovery below baseline, reducing intensity"
  adjustment_source: 'plan_unchanged' | 'fatigue_correction' | 'schedule_constraint' | 'adaptation_acceleration' | 'checkpoint_result'
  
  // Constraints for the weekly planner
  max_sessions: number | null         // audit: override value if one was applied (for observability; weekly planner reads only session_count)
  session_types_preferred: SessionType[] | null  // shift emphasis if needed
  avoid_session_types: SessionType[] | null      // e.g., avoid long runs if RED
  
  // Disruption signal (coaching only — no automatic plan adjustment)
  disruption_threshold_exceeded: boolean
  disruption_window_weeks: number                 // rolling window size (default: 3)
  disruption_rate: number                         // 0.0–1.0, rolling missed rate
  disruption_rationale: string | null             // plain-language explanation
}
```

---

## Implementation

The review is a pure Python function. All inputs are pre-computed; no LLM reasoning is required.

```python
def review_weekly_intent(input: PreWeekReviewInput) -> AdjustedWeeklyIntent:
    base = input.phase_arc_entry

    # Derive max available sessions from weekly schedule
    max_available = derive_max_available(input.athlete_preferences.weekly_schedule)

    # 1. Check recovery state
    if input.current_wellness == "red":
        session_count = compute_session_count(SessionCountInput(
            target_session_count=base.target_session_count,
            intensity_bias="easy",
            max_available=max_available,
            max_sessions=None,
        ))
        return AdjustedWeeklyIntent(
            **base,
            session_count=session_count,
            adjustment_made=True,
            adjustment_reason="Wellness state RED — reducing intensity emphasis",
            adjustment_source="fatigue_correction",
            intensity_bias="easy",
            avoid_session_types=["threshold", "vo2max"],
        )

    # 2. Check accumulated fatigue vs plan expectation
    expected_fatigue = compute_expected_fatigue(input.phase_arc_entry)
    actual_fatigue = (input.prior_weeks_summary[-1].accumulated_fatigue_delta if input.prior_weeks_summary else 0)
    if actual_fatigue > expected_fatigue * 1.2:
        session_count = compute_session_count(SessionCountInput(
            target_session_count=base.target_session_count,
            intensity_bias="easy",
            max_available=max_available,
            max_sessions=None,
        ))
        return AdjustedWeeklyIntent(
            **base,
            session_count=session_count,
            adjustment_made=True,
            adjustment_reason="Accumulated fatigue exceeds plan expectation by >20%",
            adjustment_source="fatigue_correction",
            intensity_bias="easy",
        )

    # 3. Check if adaptation signature suggests acceleration
    if input.adaptation_signature and len(input.adaptation_signature) >= 3:
        yield_data = compute_yield_by_state(input.adaptation_signature)
        if yield_data.threshold > POPULATION_MEDIAN * 1.2 and base.intensity_bias != "quality":
            session_count = compute_session_count(SessionCountInput(
                target_session_count=base.target_session_count,
                intensity_bias="moderate",
                max_available=max_available,
                max_sessions=None,
            ))
            return AdjustedWeeklyIntent(
                **base,
                session_count=session_count,
                adjustment_made=True,
                adjustment_reason="Threshold adaptation yield above median — can progress earlier",
                adjustment_source="adaptation_acceleration",
                intensity_bias="moderate",
            )

    # 4. Check checkpoint results
    recent_checkpoint = find_recent_checkpoint(input.prior_weeks_summary)
    if recent_checkpoint and recent_checkpoint.confidence_changed and recent_checkpoint.new_level == "high":
        session_count = compute_session_count(SessionCountInput(
            target_session_count=base.target_session_count,
            intensity_bias=base.intensity_bias,
            max_available=max_available,
            max_sessions=None,
        ))
        return AdjustedWeeklyIntent(
            **base,
            session_count=session_count,
            adjustment_made=True,
            adjustment_reason="Confidence upgraded — enabling more precise targets",
            adjustment_source="checkpoint_result",
        )

    # 5. Check rolling disruption rate (coaching signal — no automatic adjustment)
    disruption_rate = compute_rolling_disruption_rate(input.prior_weeks_summary)
    disruption_exceeded = disruption_rate > DISRUPTION_THRESHOLD  # 0.20

    # 6. No adjustment needed
    session_count = compute_session_count(SessionCountInput(
        target_session_count=base.target_session_count,
        intensity_bias=base.intensity_bias,
        max_available=max_available,
        max_sessions=None,
    ))
    return AdjustedWeeklyIntent(
        **base,
        session_count=session_count,
        adjustment_made=False,
        adjustment_reason=None,
        adjustment_source="plan_unchanged",
        disruption_threshold_exceeded=disruption_exceeded,
        disruption_window_weeks=DISRUPTION_WINDOW_WEEKS,  # 3
        disruption_rate=disruption_rate,
        disruption_rationale=(
            f"{disruption_rate:.0%} of sessions missed over {DISRUPTION_WINDOW_WEEKS} weeks"
            if disruption_exceeded else None
        ),
    )
```

### Disruption Computation

```python
# Configurable parameters
DISRUPTION_THRESHOLD = 0.20  # 20% of sessions missed
DISRUPTION_WINDOW_WEEKS = 3  # rolling window

def compute_rolling_disruption_rate(prior_weeks_summary: list[PriorWeekSummary]) -> float:
    """Compute rolling disruption rate over the configured window.

    Only considers weeks with data. If fewer than DISRUPTION_WINDOW_WEEKS
    have data, uses whatever is available.

    Returns: float between 0.0 and 1.0
    """
    if not prior_weeks_summary:
        return 0.0

    window = prior_weeks_summary[-DISRUPTION_WINDOW_WEEKS:]

    total_missed = sum(w.sessions_missed for w in window)
    total_completed = sum(w.sessions_completed for w in window)
    total_skipped = sum(w.sessions_skipped for w in window)

    denominator = total_completed + total_missed + total_skipped
    if denominator == 0:
        return 0.0

    return total_missed / denominator
```

---

## Decision Logic

```typescript
function reviewWeeklyIntent(input: PreWeekReviewInput): AdjustedWeeklyIntent {
  const base = input.phase_arc_entry
  
  // Derive max available sessions from weekly schedule
  const maxAvailable = deriveMaxAvailable(input.athlete_preferences.weekly_schedule)
  
  // 1. Check recovery state
  if (input.current_wellness === 'red') {
    const sessionCount = computeSessionCount({
      target_session_count: base.target_session_count,
      intensity_bias: 'easy',
      max_available: maxAvailable,
      max_sessions: null
    })
    return {
      ...base,
      session_count: sessionCount,
      adjustment_made: true,
      adjustment_reason: 'Wellness state RED — reducing intensity emphasis',
      adjustment_source: 'fatigue_correction',
      intensity_bias: 'easy',
      avoid_session_types: ['threshold', 'vo2max']
    }
  }
  
  // 2. Check accumulated fatigue vs plan expectation
  const expected_fatigue = computeExpectedFatigue(input.phase_arc_entry)
  const actual_fatigue = last(input.prior_weeks_summary)?.accumulated_fatigue_delta ?? 0
  if (actual_fatigue > expected_fatigue * 1.2) {
    const sessionCount = computeSessionCount({
      target_session_count: base.target_session_count,
      intensity_bias: 'easy',
      max_available: maxAvailable,
      max_sessions: null
    })
    return {
      ...base,
      session_count: sessionCount,
      adjustment_made: true,
      adjustment_reason: 'Accumulated fatigue exceeds plan expectation by >20%',
      adjustment_source: 'fatigue_correction',
      intensity_bias: 'easy'
    }
  }
  
  // 3. Check if adaptation signature suggests acceleration
  if (input.adaptation_signature && input.adaptation_signature.length >= 3) {
    const yield = computeYieldByState(input.adaptation_signature)
    if (yield.threshold > POPULATION_MEDIAN * 1.2 && base.intensity_bias !== 'quality') {
      const sessionCount = computeSessionCount({
        target_session_count: base.target_session_count,
        intensity_bias: 'moderate',
        max_available: maxAvailable,
        max_sessions: null
      })
      return {
        ...base,
        session_count: sessionCount,
        adjustment_made: true,
        adjustment_reason: 'Threshold adaptation yield above median — can progress earlier',
        adjustment_source: 'adaptation_acceleration',
        intensity_bias: 'moderate'
      }
    }
  }
  
  // 4. Check checkpoint results
  const recentCheckpoint = findRecentCheckpoint(input.prior_weeks_summary)
  if (recentCheckpoint?.confidence_changed && recentCheckpoint.new_level === 'high') {
    const sessionCount = computeSessionCount({
      target_session_count: base.target_session_count,
      intensity_bias: base.intensity_bias,
      max_available: maxAvailable,
      max_sessions: null
    })
    return {
      ...base,
      session_count: sessionCount,
      adjustment_made: true,
      adjustment_reason: 'Confidence upgraded — enabling more precise targets',
      adjustment_source: 'checkpoint_result'
    }
  }
  
  // 5. Check rolling disruption rate (coaching signal — no automatic adjustment)
  const disruptionRate = computeRollingDisruptionRate(input.prior_weeks_summary)
  const disruptionExceeded = disruptionRate > DISRUPTION_THRESHOLD
  
  // 6. No adjustment needed
  const sessionCount = computeSessionCount({
    target_session_count: base.target_session_count,
    intensity_bias: base.intensity_bias,
    max_available: maxAvailable,
    max_sessions: null
  })
  return {
    ...base,
    session_count: sessionCount,
    adjustment_made: false,
    adjustment_reason: null,
    adjustment_source: 'plan_unchanged',
    disruption_threshold_exceeded: disruptionExceeded,
    disruption_window_weeks: DISRUPTION_WINDOW_WEEKS,
    disruption_rate: disruptionRate,
    disruption_rationale: disruptionExceeded
      ? `${(disruptionRate * 100).toFixed(0)}% of sessions missed over ${DISRUPTION_WINDOW_WEEKS} weeks`
      : null
  }
}
```

---

## Adjustment Sources

| Source | Condition | Typical Adjustment |
|---|---|---|
| `plan_unchanged` | No deviation detected | Pass through plan intent |
| `fatigue_correction` | Wellness RED or accumulated fatigue >20% above plan | Reduce intensity bias, avoid hard sessions |
| `schedule_constraint` | Athlete availability reduced this week | Reduce max_sessions, prefer shorter sessions |
| `adaptation_acceleration` | Adaptation yield above median, phase allows progression | Increase intensity bias, shift toward quality |
| `checkpoint_result` | Confidence upgraded or metric updated | Enable more precise targets |

**Note:** `disruption_threshold_exceeded` is a coaching signal, not an adjustment source. It does not change the plan's tactical direction. It surfaces in the output for the coach to act on — typically initiating a conversation about workload, motivation, or external factors. See `weekly-coaching-rhythm.md` for the behavioral contract.

---

## Constraints

- **Cannot change the phase label.** The pre-week review operates within the current phase. It adjusts intensity and emphasis, not strategic direction.
- **Cannot add or remove weeks.** It only adjusts the content of the upcoming week.
- **Cannot change race schedule.** Secondary events and taper timing are plan-level decisions.
- **Adjustment reason is surfaced to the athlete.** Always in plain language, never jargon.
- **Disruption signal does not trigger automatic restructuring.** When `disruption_threshold_exceeded` is true, the system surfaces a coaching signal. The coach decides whether to initiate a conversation and potentially adjust the plan. The weekly synthesis agent receives this signal but does not act on it automatically.

---

## Failure Semantics

| Scenario | Behaviour |
|---|---|
| Service unavailable | Fall back to plan's original intent (no adjustment) |
| Invalid input data | Fall back to plan's original intent |
| No prior weeks data (week 1) | Pass through plan intent unchanged |

---

## Idempotency

- **Deterministic.** Same inputs always produce the same output.
- Different inputs may produce different adjustments.

---

## Events

### Produced

| Event | Trigger | Version | Payload |
|---|---|---|---|
| `pre_week_review_completed` | Review finished | v1 | `{training_plan_id, week_number, adjustment_made, adjustment_source, disruption_threshold_exceeded}` |

Note: The payload contains `training_plan_id` and `week_number`, not `weekly_plan_id`. The WeeklyPlan does not exist yet at the time of the review. The weekly synthesis agent uses these fields to look up the phase arc entry and create the WeeklyPlan. The `disruption_threshold_exceeded` field is a boolean coaching signal — it does not trigger automatic plan changes.

### Consumed

| Event | Action | Version |
|---|---|---|
| `week_completed` | Trigger review for next week | v1 |
| `training_plan_generated` | Subscribed but does NOT trigger a review for week 1. Week 1 has no prior execution data, so review is unnecessary. PlanGenerationService creates the first WeeklyPlan atomically with the plan. PreWeekReviewAgent begins acting on `week_completed` events starting from week 1's completion (i.e., reviews start at week 2). | v1 |

---

## Decision Authority

Implements the **Plan Modification Authority** authority boundary from `docs/vision/coach/decision-authority.md`.

Plan modifications are coach decisions, not athlete requests. The athlete sees the adjustment and understands the rationale, but does not initiate replanning. This agent adjusts weekly intent deterministically based on fatigue, adaptation, and checkpoint data. The constraints it respects — cannot change phase label, cannot add or remove weeks, cannot change race schedule — enforce the boundary between weekly tactical adjustment and strategic plan modification. The disruption signal (`disruption_threshold_exceeded`) is surfaced as a coaching signal for the coach to act on, not as an automatic plan change. Most day-to-day adjustments (missed sessions, schedule changes, slower-than-expected recovery) are absorbed by the weekly coaching rhythm without modifying the plan itself.

---

## Cross-References

- Decision authority: `docs/vision/coach/decision-authority.md` → "Plan Modification Authority"
- Plan phase arc: `01-entities/training-plan.md` → `phase_arc`
- Weekly synthesis: `03-agents/weekly-synthesis-agent.md`
- Wellness state: `02-computations/wellness-modifier.md`
- Adaptation signature: `01-entities/adaptation-signature.md`
- Confidence model: `00-foundations/confidence-model.md`
- Prior weeks summary: `01-entities/weekly-plan.md`
- Disruption threshold semantics: `docs/vision/product/weekly-coaching-rhythm.md` → "What Changes and What Doesn't"

## Design Notes

- Week 1 has no prior execution data, so the pre-week review is unnecessary. PlanGenerationService creates the first WeeklyPlan atomically with the phase arc.
- The adjustment explanation surfaced to the athlete is generated via templates, not LLM narration.
- The deterministic rule hierarchy (wellness → fatigue → adaptation → checkpoint) is a design decision. If the priority order needs adjustment, update the rules directly.
