# 3c — Menstrual Cycle Integration
*CyclePhaseLog, phase computation, modifier stacking, structural flag*

## Objective

Integrate menstrual cycle phase as a first-class physiological modifier — not a
separate feature but a genuine input to the recovery modifier composite. Female
athletes who log their cycle start date receive coaching that accounts for
hormonal context with no additional daily input required.

## Scope

`CyclePhaseLog` model. Phase computation service. Cycle phase composite adjustment
stacked onto the recovery modifier. Luteal thermoregulatory modifier. Ovulatory
phase structural load flag. Coach prompt to log next cycle start.

## Non-Goals

- Personalised phase boundary learning (replacing population defaults with
  individual cycle length) — requires 3 complete logged cycles; deferred to 4f
- Cycle phase referenced in coach messages — deferred to 4e
  (coach messages gain wellness context awareness in 4e)

## Architecture References

- `CyclePhaseLog` model and phase computation:
  `architecture/wellness-and-modifiers.md` → Menstrual Cycle Integration
- Phase composite adjustments (population priors):
  `architecture/wellness-and-modifiers.md` → Integration With Recovery Modifier
- Luteal thermoregulatory modifier:
  `architecture/wellness-and-modifiers.md` → Thermoregulatory Modifier — Luteal Phase
- Ovulatory structural load flag:
  `architecture/wellness-and-modifiers.md` → Structural Load Flag — Ovulatory Phase
- Vision-level implementation philosophy (low friction, athlete flags day one):
  `vision/twin/womens-cycle.md` → Implementation — Low Friction by Design

## Dependencies

Requires 3b (`WellnessModifierService` composite scoring exists).
Requires 1a (`AthleteProfile.sex` field exists — cycle tracking only activates
for athletes with `sex = female`).

## Models Introduced

**`CyclePhaseLog`** — one record per reported cycle start.
Fields: `athlete_id` FK, `cycle_day_one_date` (date), `logged_at`,
`logged_by` (enum: `athlete_self_report`, `coach_prompt_response`).
No unique constraint — multiple cycles accumulate over time.
Index on `(athlete_id, cycle_day_one_date)`.

## Services & Tasks Introduced

**`CyclePhaseService`** (sync, Python) — computes current phase.
- `get_current_phase(athlete_id, date) → (CyclePhase, int)`
  Returns `(phase, cycle_day_number)`. Returns `(unknown, 0)` if no `CyclePhaseLog`
  exists or most recent log is > 45 days ago.
  Phase boundaries use default 28-day model until personalised in 4f.

**`CyclePromptScheduler`** (async task — scheduled weekly).
- For female athletes with an active CyclePhaseLog: if ~21 days have elapsed
  since the most recent log, enqueues a prompt task.
- Creates a `CoachingMessage` with `message_type = cycle_check_in` asking the
  athlete to confirm their next cycle start date.
  Message is brief, plain-language, never clinical.

## Services Modified

**`WellnessModifierService`** (updated) — before returning the composite score,
calls `CyclePhaseService.get_current_phase()` for athletes with `sex = female`.
Applies the phase-specific composite adjustment from the arch reference.
The luteal thermoregulatory modifier is added to `heat_index_c` for downstream
weather computation in 3d (stored on a context object, not a separate field).

**`FitIngestionTask`** (updated) — for athletes in the ovulatory phase,
adds `elevated_laxity_risk: true` to `Activity.quality_flags` during ingestion.

## Endpoints Introduced

- `POST /athletes/{athlete_id}/cycle` — athlete logs cycle day one.
  Creates `CyclePhaseLog` with `logged_by = athlete_self_report`.
  Protected by `require_self`. Returns 403 if `AthleteProfile.sex ≠ female`.
- `GET /athletes/{athlete_id}/cycle/current` — returns current phase and cycle day.
  Protected by `require_self`.

## Key Constraints

- Cycle tracking is strictly opt-in via the `POST /cycle` endpoint.
  It activates only for `sex = female` athletes who have logged at least one entry.
  Athletes with `sex ≠ female` or who have never logged receive `phase = unknown`
  and the cycle modifier is not applied.
- The luteal thermoregulatory modifier is a temperature offset added to
  `heat_index_c` before weather adjustment computation — it stacks additively
  because the physiological mechanisms are distinct.
- The composite adjustment values are population-level priors (defined in arch reference).
  Personalised learning deferred to 4f.
- `CyclePromptScheduler` only creates a check-in message if no `CoachingMessage`
  with `message_type = cycle_check_in` exists and is unanswered in the past 7 days.
  No spam.

## Done Criteria

- A female athlete logging `POST /cycle` with today's date sees `phase = menstrual`
  on `GET /athletes/{id}/cycle/current`.
- On cycle day 20 (luteal phase), the workout generation agent produces adjusted
  targets that reflect the luteal composite adjustment stacked on the wellness modifier.
- An activity synced during the ovulatory phase has `elevated_laxity_risk: true`
  in `quality_flags`.
- An athlete with `sex = male` receives 403 on `POST /cycle`.
- After 21 days with no new log, a cycle check-in `CoachingMessage` is created.
