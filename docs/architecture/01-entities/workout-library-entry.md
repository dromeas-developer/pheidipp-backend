# WorkoutLibraryEntry — Curated Session Substitution Template

## Purpose
- A curated workout template used by the substitution flow when an athlete cannot do their planned session
- Not athlete-facing for browsing; returned only by the substitutes endpoint
- Accumulates acceptance signal over time; high-performing entries surface more frequently

## TypeScript Schema

```typescript
type LibraryEntrySource = 'seed' | 'generated'

type WorkoutLibraryEntry = {
  id: string                            // UUID, PK
  session_type: SessionType
  approximate_duration_minutes: number
  data_tier_minimum: DataTier           // entries requiring power targets are Tier 1-2 only
  phase_labels: PhaseLabel[]            // which plan phases this entry is appropriate for
  steps: EmbeddedStep[]                 // same structure as WorkoutStep; no FK
  intent_description: string
  times_offered: number                 // incremented each time returned as substitute
  times_accepted: number                // incremented when athlete selects
  acceptance_rate: number               // computed: times_accepted / times_offered; 0 if never offered
  created_at: string
  created_by: LibraryEntrySource
}

type EmbeddedStep = {
  step_order: number
  step_type: StepType
  session_type: SessionType
  physiological_intent: PhysiologicalIntent
  session_purpose: SessionPurpose      // default: 'general'
  target: WorkoutTarget
  duration_seconds: number | null
  description: string
}

type WorkoutTarget = {
  signal_type: 'power' | 'gap' | 'hr' | 'description'
  primary: {
    min: number | null
    max: number | null
    unit: string
  }
  fallback: WorkoutTarget | null
  description: string  // always present; plain English
}
```

## Substitution Query Logic

`WorkoutLibraryService.find_substitutes()` filters and ranks candidates:

```typescript
function findSubstitutes(
  plannedSession: PlannedSession,
  athlete: AthleteContext,
  reason: SkipReason
): WorkoutLibraryEntry[] {
  const compatible_types = getCompatibleTypes(plannedSession.session_type, reason)
  // e.g. threshold → [threshold, tempo] when reason = 'time_constraint'

  return entries
    .filter(e =>
      compatible_types.includes(e.session_type) &&
      e.approximate_duration_minutes >= plannedSession.approximate_duration_minutes * 0.8 &&
      e.approximate_duration_minutes <= plannedSession.approximate_duration_minutes * 1.2 &&
      e.data_tier_minimum <= athlete.data_tier &&
      e.phase_labels.includes(plannedSession.phase_label)
    )
    .sort((a, b) => b.acceptance_rate - a.acceptance_rate)
    .slice(0, 3)
}
```

## Promotion from Generated to Library

A `GeneratedWorkout` is promoted to `WorkoutLibraryEntry` (with `created_by = 'generated'`) when:
- It has been offered as a substitute ≥ 3 times
- Its `acceptance_rate ≥ 0.6`

This promotion runs as a nightly task — not immediately.

## Invariants
- `EmbeddedStep` uses the same field structure as `WorkoutStep` but is stored as JSONB within the entry, not as a FK-linked table. Library entries are templates, not parent-linked records.
- `physiological_intent` on each `EmbeddedStep` is never null.
- `target_gap_sec_per_km` is always GAP — never raw pace.
- No athlete contributes to the library. `created_by = 'athlete'` does not exist.
- Minimum 3 seed entries per `session_type` at initialisation.

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `workout_library_entries` table | mutable (acceptance counters) | strong | indefinite |

## Mutation Rules
| Layer | Read | Write | Delete |
|---|---|---|---|
| API | Via substitutes endpoint | No | No |
| Service | Yes | times_offered, times_accepted, acceptance_rate | No |
| Repository | Yes | Yes | No |

## Observability
Metrics:
- `workout_library.acceptance_rate.distribution`: histogram by session_type
- `workout_library.entries.by_source`: seed vs generated counts

## Cross-References

### Vision Implementation

- Vision: `docs/vision/coach/substitution.md` → "Workout Library"
- The vision describes curated templates that athletes cannot browse — this entity enforces that boundary via `created_by` invariant (`'athlete'` does not exist)
- Vision learning statement ("sessions that work well surface more frequently") maps to `acceptance_rate` sorting in `find_substitutes()`

### Invocation Chain

- Invoked by: `03-agents/skip-conversation-agent.md` via `SkipFlow 'offer_redistribution'`
- Agent classifies skip reason → routes to `offer_redistribution` → `WorkoutLibraryService.find_substitutes()` queries this entity
- Related skip flows (`no_redistribution`, `injury_escalation`, `illness_handling`) do not invoke the library — they route to plan adjustment or regeneration

### Promotion Source

- Promotes from: `GeneratedWorkout` (nightly task, ≥3 offers, ≥0.6 acceptance rate)
- Promotion logic: `02-computations/workout-promotion.md`
