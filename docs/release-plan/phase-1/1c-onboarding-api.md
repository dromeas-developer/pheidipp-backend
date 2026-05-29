# 1c — Onboarding API & Twin Bootstrap
*Questionnaire intake, atomic transaction, Tier 3 twin initialisation*

## Objective

Accept the onboarding questionnaire and produce the initial system state in one
atomic transaction: `AthletePreferences`, `TrainingBlock`, `TwinState`, and the
`onboarding_complete` flag all succeed or none are committed. The twin initialises
from population norms — no real training data, no LLM involvement, pure Python.

## Scope

Onboarding API endpoint (single round-trip). `AthletePreferences` creation.
`TrainingBlock` creation with 409 guard. Tier 3 twin initialisation as a Python
service. `TwinState` creation. `onboarding_complete` flag set to true.
Twin and plan status endpoints.

## Non-Goals

- `TrainingPlan` generation — deferred to 1d
- First coach message — deferred to 1e
- Workout generation — deferred to 1e
- Any LLM call in this sub-phase
- Cold start Tier 1 or Tier 2 (no athlete base yet)
- Menstrual cycle tracking — deferred to 3c
  (sex field is captured on AthleteProfile at registration; cycle prompt is a Phase 3 feature)

## Architecture References

- `TwinState` append-only invariant and Tier 3 bootstrap: `architecture/twin-state.md`
- Confidence level transitions: `architecture/twin-state.md` → Confidence Level Transitions
- `AthletePreferences` and `TrainingBlock` full field spec:
  `architecture/planning-and-sessions.md` → Core Domain Models
- Data tier inference from hardware: `architecture/load-and-thresholds.md` → Data Tier
- Crossover athlete structural risk flag: `architecture/planning-and-sessions.md`
  → Crossover Athlete Structural Capacity Ramp

## Dependencies

Requires 1a (all models), 1b (auth — onboarding endpoint is authenticated).

## Models Modified

**`Athlete`** — `onboarding_complete` set to `true` within the transaction.
No new fields.

## Services & Tasks Introduced

**`OnboardingService`** (sync, transactional) — orchestrates the atomic transaction.
Calls `AthletePreferencesService`, `TrainingBlockService`, `TwinBootstrapService`
in sequence within one database transaction. Sets `onboarding_complete = True`.
Returns composite onboarding response.

**`AthletePreferencesService`** (sync) — creates or updates `AthletePreferences`.
- `create(athlete_id, data) → AthletePreferences`
- `get(athlete_id) → AthletePreferences`
- `update(athlete_id, data) → AthletePreferences` (PATCH — restricted fields only)

**`TrainingBlockService`** (sync) — manages `TrainingBlock` lifecycle.
- `create(athlete_id, data) → TrainingBlock` — raises 409 if active block exists.
- `get_active(athlete_id) → TrainingBlock | None`
- `close(block_id, status) → TrainingBlock` — transitions to `completed` or `abandoned`

**`TwinBootstrapService`** (sync, Python only — no LLM) — produces initial TwinState.
Computation:
- Data tier: inferred from `hr_source` and `power_source` fields (see arch reference)
- Fitness score: derived from `weekly_volume_hours`, `years_structured_training`,
  `sport_background` using population lookup table. Crossover athletes receive
  high aerobic / low structural split.
- Fatigue score: zero (fresh start)
- Threshold estimates (lt1, lt2, max_hr): from age-graded population norms using
  `date_of_birth` from `AthleteProfile` and `fitness_level` from `TrainingBlock`
- `ftp_estimate_watts`: null (no power data yet)
- `vo2max_estimate`: null
- Confidence: `low`
- Trigger: `questionnaire`
- `model_version`: current pipeline version string

## Endpoints Introduced

- `POST /athletes/{athlete_id}/onboarding` — full questionnaire submission;
  triggers the atomic transaction; returns composite state including TwinState.
  Protected by `require_self`.
- `GET /athletes/{athlete_id}/onboarding` — returns current onboarding state
  (complete/incomplete, preferences, active block). Protected by `require_self`.
- `GET /athletes/{athlete_id}/twin` — returns latest TwinState.
  Protected by `require_self`.
- `GET /athletes/{athlete_id}/twin/history` — returns all TwinState records
  for the athlete, ordered by `created_at` desc. Protected by `require_self`.

## Key Constraints

- The entire onboarding sequence runs in one database transaction. If any step
  fails, all prior steps within the transaction are rolled back. The athlete
  remains in `onboarding_complete = False` state.
- Calling `POST /athletes/{athlete_id}/onboarding` when `onboarding_complete = True`
  returns 409 — re-onboarding is not supported. Athletes update preferences via PATCH.
- `TwinBootstrapService` is pure Python. No LLM call, no external API call.
  It must complete within 200ms.
- `TwinState` is inserted — never updated. The repository must not expose an update path.

## Done Criteria

- Submitting a complete questionnaire creates `AthletePreferences`, `TrainingBlock`,
  and `TwinState` in one transaction and sets `onboarding_complete = True`.
- Simulating a failure mid-transaction (e.g. DB error after preferences but before
  twin) leaves no partial records — all or nothing.
- Attempting to onboard twice returns 409.
- Attempting to create a second active `TrainingBlock` (e.g. via direct API call)
  returns 409 with a clear error message.
- `GET /athletes/{athlete_id}/twin` returns a TwinState with `confidence_level = low`
  and non-null `lt1_estimate_bpm`, `lt2_estimate_bpm`, `max_hr_estimate_bpm`.
