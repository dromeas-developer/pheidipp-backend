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
  
  // Adjustments from the review
  adjustment_made: boolean
  adjustment_reason: string | null    // "athlete recovery below baseline, reducing intensity"
  adjustment_source: 'plan_unchanged' | 'fatigue_correction' | 'schedule_constraint' | 'adaptation_acceleration' | 'checkpoint_result'
  
  // Constraints for the weekly planner
  max_sessions: number | null         // override from plan if schedule constrained
  session_types_preferred: SessionType[] | null  // shift emphasis if needed
  avoid_session_types: SessionType[] | null      // e.g., avoid long runs if RED
}
```

---

## Implementation

The review is a pure Python function. All inputs are pre-computed; no LLM reasoning is required.

```python
def review_weekly_intent(input: PreWeekReviewInput) -> AdjustedWeeklyIntent:
    base = input.phase_arc_entry

    # 1. Check recovery state
    if input.current_wellness == "red":
        return AdjustedWeeklyIntent(
            **base,
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
        return AdjustedWeeklyIntent(
            **base,
            adjustment_made=True,
            adjustment_reason="Accumulated fatigue exceeds plan expectation by >20%",
            adjustment_source="fatigue_correction",
            intensity_bias="easy",
        )

    # 3. Check if adaptation signature suggests acceleration
    if input.adaptation_signature and len(input.adaptation_signature) >= 3:
        yield_data = compute_yield_by_state(input.adaptation_signature)
        if yield_data.threshold > POPULATION_MEDIAN * 1.2 and base.intensity_bias != "quality":
            return AdjustedWeeklyIntent(
                **base,
                adjustment_made=True,
                adjustment_reason="Threshold adaptation yield above median — can progress earlier",
                adjustment_source="adaptation_acceleration",
                intensity_bias="moderate",
            )

    # 4. Check checkpoint results
    recent_checkpoint = find_recent_checkpoint(input.prior_weeks_summary)
    if recent_checkpoint and recent_checkpoint.confidence_changed and recent_checkpoint.new_level == "high":
        return AdjustedWeeklyIntent(
            **base,
            adjustment_made=True,
            adjustment_reason="Confidence upgraded — enabling more precise targets",
            adjustment_source="checkpoint_result",
        )

    # 5. No adjustment needed
    return AdjustedWeeklyIntent(
        **base,
        adjustment_made=False,
        adjustment_reason=None,
        adjustment_source="plan_unchanged",
    )
```

---

## Decision Logic

```typescript
function reviewWeeklyIntent(input: PreWeekReviewInput): AdjustedWeeklyIntent {
  const base = input.phase_arc_entry
  
  // 1. Check recovery state
  if (input.current_wellness === 'red') {
    return {
      ...base,
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
    return {
      ...base,
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
      return {
        ...base,
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
    return {
      ...base,
      adjustment_made: true,
      adjustment_reason: 'Confidence upgraded — enabling more precise targets',
      adjustment_source: 'checkpoint_result'
    }
  }
  
  // 5. No adjustment needed
  return {
    ...base,
    adjustment_made: false,
    adjustment_reason: null,
    adjustment_source: 'plan_unchanged'
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

---

## Constraints

- **Cannot change the phase label.** The pre-week review operates within the current phase. It adjusts intensity and emphasis, not strategic direction.
- **Cannot add or remove weeks.** It only adjusts the content of the upcoming week.
- **Cannot change race schedule.** Secondary events and taper timing are plan-level decisions.
- **Adjustment reason is surfaced to the athlete.** Always in plain language, never jargon.

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
| `pre_week_review_completed` | Review finished | v1 | `{training_plan_id, week_number, adjustment_made, adjustment_source}` |

Note: The payload contains `training_plan_id` and `week_number`, not `weekly_plan_id`. The WeeklyPlan does not exist yet at the time of the review. The weekly synthesis agent uses these fields to look up the phase arc entry and create the WeeklyPlan.

### Consumed

| Event | Action | Version |
|---|---|---|
| `week_completed` | Trigger review for next week | v1 |
| `training_plan_generated` | First weekly plan is created directly by PlanGenerationService atomically (no pre-week review for week 1 — no prior execution data exists). Pre-week reviews start at week 2. | v1 |

---

## Cross-References

- Plan phase arc: `01-entities/training-plan.md` → `phase_arc`
- Weekly synthesis: `03-agents/weekly-synthesis-agent.md`
- Wellness state: `02-computations/wellness-modifier.md`
- Adaptation signature: `01-entities/adaptation-signature.md`
- Confidence model: `00-foundations/confidence-model.md`
- Prior weeks summary: `01-entities/weekly-plan.md`

## Design Notes

- Week 1 has no prior execution data, so the pre-week review is unnecessary. PlanGenerationService creates the first WeeklyPlan atomically with the phase arc.
- The adjustment explanation surfaced to the athlete is generated via templates, not LLM narration.
- The deterministic rule hierarchy (wellness → fatigue → adaptation → checkpoint) is a design decision. If the priority order needs adjustment, update the rules directly.
