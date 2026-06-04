# WellnessAlertAgent — Proactive Wellness and Phase Transition Messages

## Purpose
- Generates proactive coach messages when patterns warrant speaking up unprompted
- Three message types: wellness alert, phase transition, plan regeneration notification
- All messages are frequency-gated to prevent noise

## Frequency Gates

```typescript
const FREQUENCY_GATES: Record<MessageType, number> = {
  wellness_alert:      5,  // days between messages of this type
  phase_transition:    0,  // no gate; fires once per phase (natural ~2-6 week frequency)
  plan_regeneration:   0,  // no gate; fires once per regeneration event
  confidence_upgrade:  0,  // no gate; fires once per confidence level transition
  cycle_check_in:      7   // days between prompts
}

function canSendProactiveMessage(athlete_id: string, message_type: MessageType): boolean {
  const most_recent = getMostRecentMessage(athlete_id, message_type)
  if (!most_recent) return true
  const days_since = daysBetween(most_recent.generated_at, now())
  return days_since >= FREQUENCY_GATES[message_type]
}
```

## Wellness Alert

**Trigger:** 7-night composite wellness score is AMBER or above AND no `wellness_alert` message in past 5 days.

**Context budget:** ~2k tokens

```typescript
type WellnessAlertContext = {
  // Pre-computed by WellnessModifierService (Python; not LLM)
  modifier_level: 'amber' | 'red'
  driving_signals: {
    signal: WellnessSignal
    deviation_score: number  // normalised; how many IQRs from baseline
    trend_direction: 'worsening' | 'stable' | 'improving'
  }[]
  days_in_pattern: number  // how many consecutive days at this level

  // What has already been adjusted
  target_adjustment_applied: string  // e.g. "targets scaled to amber level for today"

  // Upcoming session
  tomorrows_session: { session_type: SessionType; phase_label: PhaseLabel } | null
}
```

**Output:** One paragraph. States what was observed in plain language, what was adjusted, what to expect. No medical language. No alarmism. No questions — adjustments already made.

## Phase Transition

**Trigger:** First day of a new `phase_label` in the active `TrainingPlan`.

**Context budget:** ~1k tokens

```typescript
type PhaseTransitionContext = {
  outgoing_phase: { label: PhaseLabel; duration_weeks: number; primary_focus: string }
  incoming_phase: { label: PhaseLabel; duration_weeks: number; primary_focus: string }
  weeks_to_goal: number | null
}
```

**Output:** One paragraph. Names the new phase, explains the shift in training emphasis, sets expectations for the coming weeks. Grounding — the athlete understands where they are in the plan.

## Plan Regeneration Notification

**Trigger:** `training_plan_generated` event with `supersedes_plan_id` non-null.

**Context budget:** ~1k tokens

```typescript
type PlanRegenerationContext = {
  trigger: 'goal_date_change' | 'confidence_upgrade' | 'session_dropout'
  change_summary: string  // Python-computed description of what changed
  new_plan_overview: { phases: { label: PhaseLabel; weeks: number }[] }
}
```

## Prompt Locations
- `app/core/prompts/wellness_alert_v1.md`
- `app/core/prompts/phase_transition_v1.md`
- `app/core/prompts/plan_regeneration_v1.md`

## Performance Constraints
- p95 < 4s (small context; short output)

## Decision Authority

Implements the **Plan Modification Authority** authority boundary from `docs/vision/coach/decision-authority.md`.

Plan modifications are coach decisions, not athlete requests. This agent generates proactive coach messages (wellness alerts, phase transitions, plan regeneration notifications) that surface coaching signals to the athlete. These messages communicate what has been observed and what adjustments have been made — they do not request athlete approval. The wellness alert specifically surfaces recovery state and target adjustments already applied. The athlete sees the result of the coach's assessment, not a request for permission. The frequency gates prevent noise while preserving the coach's authority to speak up unprompted when the data warrants it.

---

## Cross-References

- Decision authority: `docs/vision/coach/decision-authority.md` → "Plan Modification Authority"
- Recovery modifier computation: `02-computations/wellness-modifier.md`
- TrainingPlan phase structure: `01-entities/training-plan.md`
- CoachingMessage frequency gate logic: `01-entities/coaching-message.md`
- Proactive message vision: `vision/coach/plan-visibility.md`
