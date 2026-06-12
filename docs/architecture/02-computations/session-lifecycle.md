# SessionLifecycleService

Drives the `PlannedSession` state machine. Handles completion, skip, miss, redistribution, checkpoint processing, and accept-substitute flows.

See `01-entities/planned-session.md` for the entity schema, state diagram, and invariants.

---

## Purpose

- Transitions `PlannedSession` status through its lifecycle
- Enforces structural rules during redistribution (same rules as plan generation)
- Processes checkpoint sessions and fires `checkpoint_completed`
- Coordinates with `SkipConversationAgent` for skip classification and flow routing
- Manages the accept-substitute flow from workout library

---

## State Transition Triggers

| Transition | Trigger | Source |
|---|---|---|
| `pending → generated` | Workout generated for this session | `workout_generated` event |
| `pending → redistributed` | Proactive move before target_date | API call |
| `generated → completed` | Activity with `planned_session_id` ingested | `activity_ingested` event |
| `generated → skipped` | Athlete signals skip | API call → `SkipConversationAgent` |
| `generated → missed` | Nightly sweep; target_date passed | `MissedSessionSweepTask` |
| `skipped → redistributed` | Redistribution window found | `find_redistribution_window()` |
| `skipped → [removed]` | Load dropped (fatigue/illness) | No redistribution offered |
| `missed → redistributed` | Athlete decides to make up session | API call |

---

## Skip Flow

When an athlete skips a session:

1. **Classify reason** — `SkipConversationAgent` receives athlete input and classifies:
   - `fatigue` → `no_redistribution` (load dropped; plan adjusts forward)
   - `time_constraint` → `offer_redistribution` (find alternative window)
   - `motivation` → `offer_redistribution` (find alternative window)
   - `external_constraint` → `offer_redistribution` (find alternative window)
   - `injury_concern` → `injury_escalation` (plan restructured via `PlanGenerationService`)
   - `illness` → `illness_handling` (conservative return ramp via `PlanGenerationService`)

2. **Route to flow** — based on classification:
   - `no_redistribution`: Session status → `skipped`. No new session created. Plan adjusts forward.
   - `offer_redistribution`: Call `find_redistribution_window()` to find alternatives. Present options to athlete.
   - `injury_escalation`: Call `PlanGenerationService.regenerate()` with injury flag. Plan restructured.
   - `illness_handling`: Call `PlanGenerationService.regenerate()` with illness flag. Next 3 sessions after return forced to easy/recovery.

3. **Persist** — Set `skip_reason` on the `PlannedSession`. Fire `session_skipped` event.

---

## Redistribution

### Finding a Window

`find_redistribution_window()` searches for a valid target date:

```
For each candidate date after skip:
  1. Check structural rules (same validation as plan generation):
     - No consecutive quality sessions (unless block_id shared)
     - Long run followed by rest/recovery
     - Threshold/vo2max sandwiched between easy/rest days
     - Recovery window from primary to primary
  2. Check athlete availability (available days from preferences)
  3. Check slot capacity (no duplicate slot on same date)
  4. If valid → return as candidate
```

If no window found within 7 days → session remains `skipped` (load dropped).

### Executing Redistribution

1. Set original session status → `redistributed`, `redistributed_to_date` = target
2. Create new `PlannedSession` for target date with `status = 'pending'`
3. New session inherits: `session_type`, `intent_description`, `approximate_duration_minutes`, `checkpoint_type`, `checkpoint_metric`, `block_id` (if applicable)
4. Fire `session_skipped` event with `redistributed_to_date`

---

## Accept-Substitute Flow

When an athlete accepts a library substitute:

1. **Query library** — `WorkoutLibraryService.find_substitutes()` returns up to 3 matching entries
2. **Create workout** — `GeneratedWorkout` is created from the library entry's embedded steps
3. **Link to session** — The `PlannedSession` remains linked to the original planned session. No new `PlannedSession` is created.
4. **Fire event** — `workout_generated` event transitions status → `generated`

The `is_suggested` flag distinguishes suggested non-running sessions from full workouts.

---

## Checkpoint Processing

When a checkpoint session completes:

1. **Session completes** — `activity_ingested` event transitions `PlannedSession` → `completed`
2. **Process checkpoint** — `SessionLifecycleService` processes the checkpoint atomically:
   - Analyse activity data against `checkpoint.target_metric`
   - Update twin state if metric changed materially
   - Check if confidence level changed
   - Set completion fields: `metric_updated`, `confidence_changed`, `replan_triggered`, `completed_at`
3. **Fire event** — `checkpoint_completed` event with full result payload
4. **Downstream consumers**:
   - `PlanGenerationService.evaluate_replan()` — if `replan_triggered = true`
   - `ProactiveMessageService.check_checkpoint_result()` — athlete notification

---

## Nightly Miss Sweep

`MissedSessionSweepTask` runs nightly:

1. Find all `PlannedSession` records where `status = 'generated'` AND `target_date < today`
2. Transition each to `status = 'missed'`
3. Fire `session_missed` event for each

**Scope:** Only touches sessions with `status = 'generated'` (workout was shown to athlete). Never touches `pending` sessions that were not yet due.

**WeeklySession handling:** WeeklySession records are stored in the `weekly_sessions` table with a FK to `WeeklyPlan`. When a workout is generated for a session, the `planned_session_id` FK is set on the WeeklySession. Sessions that were never promoted to PlannedSession (workout never generated) have `planned_session_id = null` and `status = 'scheduled'`. These orphaned sessions are handled by the weekly plan completion logic, not by MissedSessionSweepTask. See `01-entities/weekly-plan.md` for the full handling strategy.

---

## Disruption Tracking

The service tracks disruption rates for pre-week review:

| Metric | Calculation | Usage |
|---|---|---|
| `skip_rate` | skipped / (completed + skipped) | Per session_type |
| `miss_rate` | missed / (completed + missed + skipped) | Per phase_label |
| `rolling_disruption_rate` | Rolling 3-week missed rate | Fed to pre-week review |
| `disruption_threshold_exceeded` | Boolean, per athlete | Set by pre-week review when >20% missed over 3 weeks |

When `disruption_threshold_exceeded` fires, it surfaces as a coaching signal via `weekly-coaching-rhythm.md`. The coach decides whether to restructure.

---

## Structural Rule Enforcement

The same structural rules are enforced during:
1. **Plan generation** — `WeeklySynthesisAgent` creates sessions遵守 these rules
2. **Redistribution** — `find_redistribution_window()` validates against these rules

Rules:
- Long runs followed by rest or `recovery_run`
- Threshold/vo2max sandwiched between easy/rest days
- No two quality sessions on consecutive dates (unless shared `block_id`)
- Block members must be consecutive, all quality, max 3 sessions (enforced by `identifyBlockCandidates()` — see `03-agents/weekly-synthesis-agent.md` → Block Creation Logic)
- Block must include recovery after final session
- Recovery time measured primary-to-primary

---

## Failure Semantics

| Scenario | Behaviour |
|---|---|
| Redistribution target violates structural rules | 422 with specific rule violated |
| Redistribution target is in the past | 422 |
| Nightly sweep failure | Sessions remain `generated`; swept on next run |
| Skip classification low confidence | Default to `external_constraint` → `offer_redistribution` |
| No redistribution window found within 7 days | Session remains `skipped` (load dropped) |

---

## Cross-References

- **Entity schema and state machine:** `01-entities/planned-session.md`
- **Skip classification:** `03-agents/skip-conversation-agent.md`
- **Checkpoint entity:** `01-entities/checkpoint.md`
- **Workout library substitution:** `01-entities/workout-library-entry.md`
- **Plan regeneration:** `02-computations/plan-generation.md`
- **Pre-week review (disruption signal):** `03-agents/pre-week-review-agent.md`
- **Coaching rhythm (disruption threshold):** `03-agents/weekly-coaching-rhythm.md`
- **Vision substitution flows:** `docs/vision/product/substitution.md`
