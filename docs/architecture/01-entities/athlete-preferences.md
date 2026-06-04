# AthletePreferences — Mutable Training Configuration

## Purpose
- Stores the athlete's training setup, hardware, schedule availability, and platform connections
- Drives data tier inference, plan session distribution, and wellness modifier time-of-day correction
- Mutable via PATCH; changes affect future plan generation but never historical analysis

## TypeScript Schema

```typescript
type SportBackground =
  | 'running_primary' | 'cycling' | 'swimming'
  | 'triathlon' | 'team_sport' | 'gym_fitness' | 'none'

type TrainingTimeOfDay = 'morning' | 'afternoon' | 'evening' | 'variable'

type GpsSource =
  | 'garmin_watch' | 'apple_watch' | 'polar'
  | 'suunto' | 'coros' | 'other'

type HrSource =
  | 'chest_strap_rr'      // enables RR intervals → Tier 1 or 3
  | 'chest_strap_no_rr'   // HR only → Tier 4
  | 'wrist_optical'       // HR only → Tier 4
  | 'none'                // no HR → Tier 5

type PowerSource = 'running_power_meter' | 'none'

type PrimaryTrainingPlatform = 'intervals_icu' | 'garmin_connect' | 'manual'

type DaySchedule = {
  available: boolean
  max_hours: number        // ignored if available = false
  long_workout: boolean    // marks the day as eligible for long run placement
}

type WeeklySchedule = {
  monday: DaySchedule
  tuesday: DaySchedule
  wednesday: DaySchedule
  thursday: DaySchedule
  friday: DaySchedule
  saturday: DaySchedule
  sunday: DaySchedule
}

type AthletePreferences = {
  id: string                        // UUID, PK
  athlete_id: string               // UUID, FK → Athlete, one-to-one
  sport_background: SportBackground
  years_structured_training: number  // >= 0
  training_time_of_day: TrainingTimeOfDay
  weekly_schedule: WeeklySchedule
  gps_source: GpsSource
  hr_source: HrSource
  power_source: PowerSource
  primary_training_platform: PrimaryTrainingPlatform
  updated_at: string               // ISO 8601
}
```

## Invariants
- One `AthletePreferences` per `Athlete`. Created during onboarding. Enforced by unique constraint on `(athlete_id)`.
- `years_structured_training >= 0`. CHECK constraint at DB level.
- No DELETE endpoint. Preferences are always present once onboarding completes.
- `sport_background` not `running_primary` activates the crossover athlete structural capacity ramp in plan generation. See `02-computations/plan-generation.md` (shared types) and `02-computations/plan-generation-race.md` (race mode ramp).
- `training_time_of_day` feeds the time-of-day modifier in `WellnessModifierService`. See `02-computations/wellness-modifier.md`.
- `hr_source` is the primary input for data tier inference. See `00-foundations/data-tiers.md`.
- Changes to `hr_source` or `power_source` affect the data tier of the next ingested Activity but do not retroactively alter historical Activities.
- `weekly_schedule` is stored as structured JSONB. Each day's `available` and `max_hours` directly constrain `PlanGenerationService` session distribution.

## Data Tier Inference

```typescript
function inferDataTier(prefs: AthletePreferences): DataTier {
  if (prefs.power_source === 'running_power_meter') {
    return prefs.hr_source === 'chest_strap_rr' ? 1 : 2
  }
  if (prefs.hr_source === 'chest_strap_rr') return 3
  if (prefs.hr_source === 'chest_strap_no_rr' || prefs.hr_source === 'wrist_optical') return 4
  if (prefs.hr_source === 'none') return 5
  return 6
}
```

## Events

### Produced
| Event | Trigger | Version | Payload |
|---|---|---|---|
| None | — | — | — |

### Consumed
| Event | Action | Version |
|---|---|---|
| `onboarding_completed` | Preferences already written; no action | v1 |

## APIs

```yaml
POST /athletes/{athlete_id}/preferences
Description: Created during onboarding; not a standalone endpoint
Response: embedded in onboarding response

GET /athletes/{athlete_id}/preferences
Response: 200
  preferences: AthletePreferences
Auth: Bearer JWT, require_self

PATCH /athletes/{athlete_id}/preferences
Request:
  # any subset of AthletePreferences fields
  sport_background?: SportBackground
  years_structured_training?: number
  training_time_of_day?: TrainingTimeOfDay
  weekly_schedule?: Partial<WeeklySchedule>
  gps_source?: GpsSource
  hr_source?: HrSource
  power_source?: PowerSource
  primary_training_platform?: PrimaryTrainingPlatform
Response: 200
  preferences: AthletePreferences
Note: Changes to hr_source or power_source may trigger plan regeneration
     if the data tier ceiling changes materially.
Auth: Bearer JWT, require_self
```

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `athlete_preferences` table | mutable (PATCH) | strong | indefinite |

Unique constraint: `(athlete_id)` — one record per athlete.

Changes are not versioned — only `updated_at` is tracked. Historical preference states are not retained. This is intentional: preferences affect future plan generation, not historical analysis.

## Mutation Rules
| Layer | Read | Write | Delete |
|---|---|---|---|
| API | Yes | PATCH only | No |
| Service | Yes | Yes | No |
| Repository | Yes | Yes | No |

## Runtime Ownership
Owns:
- Hardware and platform configuration
- Weekly schedule availability
- Data tier ceiling inference

Does Not Own:
- Data tier assigned to a specific Activity (that is inferred per-session at ingestion)
- Plan generation decisions → `02-computations/plan-generation.md`
- Wellness modifier time-of-day correction → `02-computations/wellness-modifier.md`

## Failure Semantics
- PATCH with invalid `weekly_schedule` (e.g. `max_hours < 0`) → 422 Unprocessable Entity
- PATCH that changes `hr_source` or `power_source` → triggers async plan regeneration check; PATCH response returns immediately

## Performance Constraints
- `GET /athletes/{id}/preferences`: p95 < 50ms
- `PATCH /athletes/{id}/preferences`: p95 < 100ms

## Observability
Metrics:
- `athlete_preferences.data_tier.distribution`: count by tier (monitoring hardware adoption)
Logs:
- `athlete_preferences.updated`: athlete_id, changed_fields, new_data_tier

## Implementation Notes
- `weekly_schedule` partial PATCH merges at the day level — sending `{saturday: {available: false}}` disables Saturday without touching other days
- Plan generation reads `weekly_schedule` to determine which days can receive sessions and which day receives the long run (`long_workout: true`)
- The crossover athlete flag is derived from `sport_background !== 'running_primary'` — no separate boolean field
