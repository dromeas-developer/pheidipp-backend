# ContextBudgetService — Context Assembly and Token Enforcement

## Purpose
- Assembles the structured context digest for each agent
- Enforces token budgets before the LLM API call — never discovers overrun from the response
- Applies priority ordering when content exceeds budget

## Context Builders

```typescript
class ContextBudgetService {

  // For FirstMessageAgent
  async buildFirstMessageContext(athlete_id: string): Promise<FirstMessageContext> {
    const twin_state = await TwinStateRepository.get_latest(athlete_id)
    const training_block = await TrainingBlockRepository.get_active(athlete_id)
    const preferences = await AthletePreferencesRepository.get(athlete_id)
    const profile = await AthleteProfileRepository.get(athlete_id)
    const plan = await TrainingPlanRepository.get_active(athlete_id)

    const context = {
      readiness: TwinContextAssemblerService.assemble(twin_state),
      computed_observations: computeOnboardingObservations(twin_state, preferences),
      goal_summary: buildGoalSummary(training_block),
      profile_summary: buildProfileSummary(profile, preferences),
      plan_overview: buildPlanOverview(plan),
      first_block_preview: buildFirstBlockPreview(plan)
    }

    return this.enforce_budget(context, MAX_TOKENS.first_message)
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

    return this.enforce_budget(context, MAX_TOKENS.workout_generation)
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

    return this.enforce_budget(context, MAX_TOKENS.post_workout)
    // Target: 3k–6k tokens
  }
}
```

## Token Budget Enforcement

```typescript
const MAX_TOKENS = {
  first_message:       5000,
  workout_generation:  3000,
  post_workout:        6000,
  skip_conversation:   1000,
  wellness_alert:      2000,
  phase_transition:    1000,
  plan_regeneration:   1000
}

// Priority ordering when context exceeds budget:
// Post-workout: current execution > comparable session > objective updates > plan context
// First message: computed observations > goal summary > plan overview > first block preview
// Workout generation: session intent > readiness > objectives

function enforce_budget<T>(context: T, max_tokens: number): T {
  const estimated = estimateTokens(context)
  if (estimated <= max_tokens) return context
  // Apply priority truncation: remove lower-priority sections until within budget
  // Never truncate the section that contains the specific execution findings
}
```

## Cross-References
- TwinContextAssemblerService: `01-entities/twin-state.md` → Context Assembly
- All agent context types: `03-agents/first-message-agent.md`, `03-agents/post-workout-agent.md`, `03-agents/workout-generation-agent.md`
- Token budget invariant: `00-foundations/principles.md`
