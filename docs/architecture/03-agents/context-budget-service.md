# ContextBudgetService

- Assembles the structured context digest for each agent
- Enforces token budgets before the LLM API call — never discovers overrun from the response
- Applies priority ordering when content exceeds budget

---

## Context Builders

```typescript
class ContextBudgetService {

  // For FirstMessageAgent
  async buildFirstMessageContext(athlete_id: string): Promise<FirstMessageContext> {
    const twin_state = await TwinStateRepository.get_latest(athlete_id)
    const training_goal = await TrainingGoalRepository.get_active(athlete_id)
    const preferences = await AthletePreferencesRepository.get(athlete_id)
    const profile = await AthleteProfileRepository.get(athlete_id)
    const plan = await TrainingPlanRepository.get_active(athlete_id)

    const context = {
      readiness: TwinContextAssemblerService.assemble(twin_state),
      computed_observations: computeOnboardingObservations(twin_state, preferences),
      goal_summary: buildGoalSummary(training_goal),
      profile_summary: buildProfileSummary(profile, preferences),
      plan_overview: buildPlanOverview(plan),
      first_block_preview: buildFirstBlockPreview(plan)
    }

    return this.enforce_budget(context, MAX_TOKENS.first_message, 'FirstMessageAgent')
    // Target: 3k–5k tokens
  }

  // For WorkoutGenerationAgent
  async buildWorkoutContext(
    athlete_id: string,
    planned_session_id: string
  ): Promise<WorkoutGenerationContext> {
    const twin_state = await TwinStateRepository.get_latest(athlete_id)
    const planned_session = await PlannedSessionRepository.get(planned_session_id)
    const recovery_modifier = await WellnessModifierService.classify(athlete_id, today())
    const cycle_adjustment = await CyclePhaseService.get_current_phase(athlete_id, today())
    const weather = await WeatherForecastRepository.get(athlete_id, today())
    const objectives = await ObjectiveRepository.get_for_session(planned_session.session_type)

    const context = {
      session: buildSessionSummary(planned_session),
      readiness: TwinContextAssemblerService.assemble(twin_state, recovery_modifier),
      data_tier: twin_state.data_tier,
      target_type: inferTargetType(twin_state.data_tier),
      relevant_objectives: objectives.slice(0, 2)
    }

    return this.enforce_budget(context, MAX_TOKENS.workout_generation, 'WorkoutGenerationAgent')
    // Target: 2k–3k tokens
  }

  // For PostWorkoutAgent
  async buildPostWorkoutContext(
    athlete_id: string,
    activity_id: string
  ): Promise<PostWorkoutContext> {
    const activity = await ActivityRepository.get(activity_id)
    const planned_session = await PlannedSessionRepository.get(activity.planned_session_id)
    const execution = await ExecutionObservationRepository.get_by_activity(activity_id)
    const compliance = ComplianceService.compute(activity, planned_session)
    const comparable = await ComparableSessionService.find(activity)
    const objective_updates = await ObjectiveUpdateRepository.get_recent_for_session(
      athlete_id, planned_session.session_type
    )
    const twin_state = await TwinStateRepository.get_latest(athlete_id)

    const context = {
      prescribed: buildPrescribedSummary(planned_session),
      compliance,
      execution: execution?.coaching_observations ?? null,
      comparable_session: comparable
        ? ComparableSessionService.build_summary(comparable)
        : null,
      objective_updates: buildObjectiveUpdateSummary(objective_updates),
      readiness_summary: buildReadinessSummary(twin_state, planned_session)
    }

    return this.enforce_budget(context, MAX_TOKENS.post_workout, 'PostWorkoutAgent')
    // Target: 3k–6k tokens
  }
}
```

---

## Token Budget Enforcement

```typescript
// Token estimation — simple, no external dependencies
function estimateTokens(obj: unknown): number {
  return Math.ceil(JSON.stringify(obj).length / 4)
}

const MAX_TOKENS = {
  first_message:       5000,
  workout_generation:  3000,
  post_workout:        6000,
  skip_conversation:   1000,
  wellness_alert:      2000,
  phase_transition:    1000,
  plan_regeneration:   1000
}

// Priority-weighted truncation — removes lowest-weight sections first
function enforce_budget<T>(context: T, max_tokens: number, agent: AgentType): T {
  const estimated = estimateTokens(context)
  if (estimated <= max_tokens) return context
  
  const profile = AGENT_PRIORITY_PROFILES[agent]
  const truncated = applyWeightedTruncation(context, max_tokens, profile)
  const finalEstimate = estimateTokens(truncated)
  
  if (finalEstimate > max_tokens) {
    // Log warning, but proceed — degraded context is better than no context
    logger.warn('Context budget exceeded after truncation', {
      agent, estimated: finalEstimate, max: max_tokens
    })
  }
  
  return truncated
}

// Truncation helper — removes sections from lowest weight upward
function applyWeightedTruncation<T>(
  context: T, 
  max_tokens: number, 
  profile: ContextSection[]
): T {
  let current = { ...context }
  let estimate = estimateTokens(current)
  
  // Sort by priority weight ascending (lowest weight = first to remove)
  const sorted = [...profile].sort((a, b) => a.priority_weight - b.priority_weight)
  
  for (const section of sorted) {
    if (estimate <= max_tokens) break
    if (current[section.name] !== undefined) {
      delete current[section.name]
      estimate = estimateTokens(current)
    }
  }
  
  // If still over budget, truncate string values in remaining sections
  if (estimate > max_tokens) {
    current = truncateStrings(current, max_tokens)
  }
  
  return current
}

function truncateStrings(obj: unknown, max_tokens: number): unknown {
  // Recursively truncate long string values
  // Implementation detail — keeps structure, shortens content
}
```

---

## Invariants

- Token estimation uses `JSON.stringify(obj).length / 4` — deterministic, no external dependencies
- **Priority-Weighted Truncation:** Each context section declares a priority weight (1–100). Truncation removes lowest-weight sections first. Priority weights are agent-specific, not global.
  
  ```typescript
  type ContextSection = {
    name: string
    priority_weight: number  // 1–100; higher = more important
    token_budget: number     // estimated tokens
  }
  
  const AGENT_PRIORITY_PROFILES: Record<AgentType, ContextSection[]> = {
    post_workout: [
      { name: 'session_summary', priority_weight: 100, token_budget: 500 },
      { name: 'objectives', priority_weight: 85, token_budget: 400 },
      { name: 'comparable_sessions', priority_weight: 75, token_budget: 600 },
      { name: 'cycle_phase', priority_weight: 70, token_budget: 150 },
      { name: 'weather', priority_weight: 60, token_budget: 200 },
      { name: 'race_prediction', priority_weight: 50, token_budget: 300 },
      // ... other sections
    ],
    // ... other agent profiles
  }
  ```
  
- **Dynamic Priority Adjustment:** Priority weights adjust based on context. Examples:
  - `weather` priority increases within 14 days of race event
  - `cycle_phase` priority increases for female athletes in luteal phase
  - `race_prediction` priority increases when trajectory is ahead or at risk
  
- **Agent-Specific Profiles:** Each agent type has its own priority profile. Profiles are defined in `AGENT_PRIORITY_PROFILES` and configured per agent, not hardcoded in truncation logic.
- If budget still exceeded after section removal, string values are truncated (structure preserved)
- No errors thrown — degraded context is always returned
- Context assembly latency: p95 < 100ms (excluding data fetch)

---

## API Endpoints

None. Context budget enforcement is an internal implementation detail of the agent orchestrators.

---

## Storage Models

None. Budget metrics are logged to the observability platform, not stored in dedicated tables.

---

## Observability

Log the following (structured logs, not database tables):

```typescript
// On every agent context assembly
logger.info('context_budget.assembled', {
  agent,
  estimated_tokens,
  max_tokens,
  within_budget: estimated_tokens <= max_tokens,
  sections_included: Object.keys(context)
})

// On truncation
logger.warn('context_budget.truncated', {
  agent,
  original_tokens: estimated,
  truncated_tokens: finalEstimate,
  max_tokens,
  sections_removed: removedSections
})
```

Metrics (via your observability platform):
- `context_budget.estimated_tokens` (histogram per agent)
- `context_budget.truncation_events` (counter per agent)
- `context_budget.assembly_latency_ms` (histogram)

---

## Cross-References

- TwinContextAssemblerService: `01-entities/twin-state.md` → Context Assembly
- All agent context types: `03-agents/first-message-agent.md`, `03-agents/post-workout-agent.md`, `03-agents/workout-generation-agent.md`
- Token budget invariant: `00-foundations/principles.md`
