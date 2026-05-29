# 4e — Proactive Coach Messages
*Wellness alerts, phase transitions, plan notifications*

## Objective

The coach speaks up unprompted when something is worth saying — a sustained
wellness pattern, a phase transition, a plan change. Until now all coach messages
have been reactive (triggered by athlete actions). This sub-phase makes the
coaching feel like an ongoing relationship rather than a query-response system.

## Scope

Proactive message triggers: wellness pattern alert, phase transition notification,
plan regeneration notification, confidence upgrade notification. New `message_type`
enum values. `ProactiveMessageService` orchestrator.

## Non-Goals

- Free Coach Chat interactive mode — deferred to post-Phase 6
- Group coaching messages — deferred to post-Phase 6

## Architecture References

- Proactive wellness alert example coach message:
  `vision/twin/external-modifiers.md` → Coach Communication
- Phase transition as coaching moment:
  `vision/coach/plan-visibility.md` → Phase Transitions
- Voice and format rules apply to all proactive messages:
  `vision/coach/voice-and-format.md`
- `CoachingMessage.message_type` enum: `architecture/data-models.md`

## Dependencies

Requires 3b (wellness modifier — wellness alerts need a pattern to report).
Requires 1d (plan phases — phase transitions need plan phase data).

## Models Modified

**`CoachingMessage.message_type`** — adds enum values:
`wellness_alert`, `phase_transition`, `plan_regeneration`, `confidence_upgrade`,
`cycle_check_in` (already used in 3c — formalised here).

## Services Introduced

**`ProactiveMessageService`** (async) — evaluates triggers and generates messages.
- `check_wellness_alert(athlete_id) → CoachingMessage | None`
  Runs after each `BaselineComputationTask`. If the 7-night deviation score is
  AMBER or above AND no `wellness_alert` message exists in the past 5 days:
  generates a proactive message via `WellnessAlertAgent`.
- `check_phase_transition(athlete_id) → CoachingMessage | None`
  Runs after `PlanGenerationService` or nightly. If today is the first day of a
  new `phase_label`: generates a phase transition message.
- `check_plan_regeneration(athlete_id, reason) → CoachingMessage | None`
  Called by `PlanGenerationService` when a plan is regenerated. Generates a
  message explaining the change.
- `check_confidence_upgrade(athlete_id, old_level, new_level) → CoachingMessage | None`
  Called by `TwinRecalibrationService` when confidence transitions. Generates a
  brief message noting that threshold estimates have updated and targets are now
  more precise.

**`WellnessAlertAgent`** (async LLM agent — ~2k token context).
Context: 7-night deviation score breakdown, the specific signals driving the pattern
(structured, pre-computed), the scheduled session for today/tomorrow.
Output: one paragraph coach message in plain language. No clinical language,
no diagnoses. States what was observed, what was adjusted, why it matters.

**`PhaseTransitionAgent`** (async LLM agent — ~1k token context).
Context: outgoing phase label and duration, incoming phase label and focus,
weeks remaining to goal event.
Output: one paragraph announcing the new phase, explaining the shift in training
emphasis, and setting expectations for the coming weeks.

## Key Constraints

- Proactive messages have frequency guards — no message type is sent more than
  once per 5 days per athlete, except `phase_transition` (natural frequency is
  every 2-6 weeks anyway).
- All proactive agents write `GenerationEvent` records.
- Proactive messages are stored as `CoachingMessage` records with the appropriate
  `message_type`. They are surfaced in the message feed alongside reactive messages.
- The wellness alert must not be alarmist. The coach adjusts targets and explains —
  it does not suggest medical consultation unless the pattern is extreme.

## Done Criteria

- After 7+ days of AMBER wellness signals with no `wellness_alert` message in
  the past 5 days, a proactive wellness message is created and surfaced.
- On the first day of a new plan phase, a phase transition message appears in the
  message feed.
- When the twin's confidence upgrades from LOW to MEDIUM, a notification message
  appears informing the athlete that targets are now more precise.
- No proactive message of the same type is created twice within 5 days.
