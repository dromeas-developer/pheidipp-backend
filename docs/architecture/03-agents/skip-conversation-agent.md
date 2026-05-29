# SkipConversationAgent — Skip Reason Classification

## Purpose
- Lightweight agent that classifies the reason for a session skip
- Context budget is intentionally small — this is a classification task, not a narrative task
- Output drives the redistribution/substitution/illness flow in SessionLifecycleService

## Context Budget: ~1k tokens

```typescript
type SkipConversationContext = {
  session: {
    session_type: SessionType
    phase_label: PhaseLabel
    approximate_duration_minutes: number
  }
  athlete_input: string  // free text from athlete; may be empty
  recent_wellness_modifier: RecoveryModifierLevel
  recent_skip_history: number  // skips in past 14 days; flags potential pattern
}
```

## Output Contract

```typescript
type SkipClassification = {
  reason: SkipReason
  confidence: number  // 0.0–1.0; low confidence → default to 'external_constraint'
  suggested_flow: SkipFlow
}

type SkipReason =
  | 'fatigue'
  | 'time_constraint'
  | 'injury_concern'
  | 'motivation'
  | 'illness'
  | 'external_constraint'

type SkipFlow =
  | 'no_redistribution'    // fatigue/illness: load dropped; plan adjusts forward
  | 'offer_redistribution' // time_constraint/motivation/external: find alternative window
  | 'injury_escalation'    // injury_concern: invoke injury handling in PlanGenerationService
  | 'illness_handling'     // illness: invoke illness flow; conservative return ramp
```

## Flow Routing by Classification

```typescript
function routeSkipFlow(classification: SkipClassification): void {
  switch (classification.suggested_flow) {
    case 'no_redistribution':
      // Plan adjusts forward; no new PlannedSession created
      break

    case 'offer_redistribution':
      const window = SessionLifecycleService.find_redistribution_window(...)
      const substitutes = WorkoutLibraryService.find_substitutes(...)
      // Return options to athlete
      break

    case 'injury_escalation':
      PlanGenerationService.regenerate(athlete_id, { injury_flag: classification.reason })
      break

    case 'illness_handling':
      PlanGenerationService.regenerate(athlete_id, { illness_flag: true })
      // Next 3 sessions after return → easy_aerobic or recovery_run
      break
  }
}
```

## Prompt Location
`app/core/prompts/skip_conversation_v1.md`

## Performance Constraints
- p95 < 3s (small context; fast classification)

## Cross-References
- PlannedSession lifecycle: `01-entities/planned-session.md`
- Session redistribution algorithm: `02-computations/plan-generation.md`
- WorkoutLibraryEntry substitution query: `01-entities/workout-library-entry.md`
