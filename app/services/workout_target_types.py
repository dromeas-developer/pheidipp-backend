"""Workout target-type and intent constants for ``WorkoutGenerationAgent``.

Phase-1.5b (Workout Generation) introduces application-level constants
that translate heterogeneous architecture decisions into the workout's
JSONB shape. The two maps live here so the agent, prompt, and
``ContextBudgetService`` share a single source of truth:

* :data:`SESSION_INTENT_MAP` — the canonical mapping from
  :class:`SessionType` to :class:`PhysiologicalIntent` documented in
  ``docs/architecture/00-foundations/terminology.md``. Mirrors the
  TypeScript reference; the agent and prompt both use these values
  when deriving intent for ``work`` steps.

* :data:`DATA_TIER_TARGET_TYPE` — maps :class:`DataTier` to the
  primary target modality surfaced in :class:`WorkoutTarget`. Tier
  1-2 athletes get ``'power'`` (running power meter available),
  Tier 3-4 athletes get ``'gap'`` (HR chest strap without RR or
  wrist optical → pace-based, GAP-enforced), and Tier 5-6 athletes
  fall back to ``'description'`` (no numeric targets).

The mapping here intentionally differs from the architecture doc's
``twin-context-assembler.md`` wording (``'effort_description'`` vs.
``'description'`` here). The plan's Step 4 spec fixes the canonical
value at ``'description'`` so the JSONB ``signal_type`` string
matches the closed ontology — the architecture alias is a doc-only
naming distinction. The ``WorkoutTarget.signal_type`` field on
generated rows uses one of ``power | gap | hr | description``.
"""

from __future__ import annotations

from app.models.enums import DataTier, PhysiologicalIntent, SessionType, StepType


# ---------------------------------------------------------------------------
# SESSION_INTENT_MAP — SessionType → PhysiologicalIntent.
# Mirrors the TypeScript reference verbatim. The ``test_session`` row
# defaults to ``vo2max`` to match the architecture spec; the agent's
# test-protocol decoding (Phase 2+) overrides this case-by-case.
# ---------------------------------------------------------------------------

SESSION_INTENT_MAP: dict[SessionType, PhysiologicalIntent] = {
    SessionType.REST: PhysiologicalIntent.RECOVERY,
    SessionType.RECOVERY_RUN: PhysiologicalIntent.RECOVERY,
    SessionType.EASY_RUN: PhysiologicalIntent.LOW_AEROBIC,
    SessionType.LONG_RUN: PhysiologicalIntent.HIGH_AEROBIC,
    SessionType.MEDIUM_LONG_RUN: PhysiologicalIntent.HIGH_AEROBIC,
    SessionType.STEADY_STATE: PhysiologicalIntent.HIGH_AEROBIC,
    SessionType.TEMPO: PhysiologicalIntent.THRESHOLD,
    SessionType.THRESHOLD: PhysiologicalIntent.THRESHOLD,
    SessionType.VO2MAX: PhysiologicalIntent.VO2MAX,
    SessionType.HILL_REPEATS: PhysiologicalIntent.VO2MAX,
    SessionType.FARTLEK: PhysiologicalIntent.VO2MAX,
    SessionType.STRIDES: PhysiologicalIntent.NEUROMUSCULAR,
    SessionType.DRILLS_MOBILITY: PhysiologicalIntent.NEUROMUSCULAR,
    SessionType.CROSS_TRAINING: PhysiologicalIntent.LOW_AEROBIC,
    SessionType.TEST_SESSION: PhysiologicalIntent.VO2MAX,
    SessionType.OPTIONAL_RUN: PhysiologicalIntent.RECOVERY,
}


# ---------------------------------------------------------------------------
# DATA_TIER_TARGET_TYPE — DataTier → target modality string.
# The plan's Step 4 fix to the architecture doc: ``'description'`` not
# ``'effort_description'``. Tier 1 / 2 → power; Tier 3 / 4 → gap;
# Tier 5 / 6 → description-only.
# ---------------------------------------------------------------------------

DATA_TIER_TARGET_TYPE: dict[DataTier, str] = {
    DataTier.TIER_1: "power",
    DataTier.TIER_2: "power",
    DataTier.TIER_3: "gap",
    DataTier.TIER_4: "gap",
    DataTier.TIER_5: "description",
    DataTier.TIER_6: "description",
}


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def get_step_physiological_intent(
    step_type: StepType, session_type: SessionType
) -> PhysiologicalIntent:
    """Return the prescribed ``PhysiologicalIntent`` for a (step, session) pair.

    Implements the architecture's "physiological_intent is never null"
    invariant from ``docs/architecture/01-entities/workout-step.md``:

    * ``warmup`` / ``cooldown`` / ``recovery`` step types always
      carry the ``recovery`` intent — these segments are scaffolding
      regardless of the parent session's purpose.
    * ``work`` step types read intent from :data:`SESSION_INTENT_MAP`
      keyed by the parent session's :class:`SessionType`.

    The agent calls this helper after parsing LLM JSON output to
    verify or fill in step intents; for ``work`` steps it provides a
    deterministic fallback the validator uses to catch drift
    between the prompt's stated and the architecture's intended
    intent.
    """
    if step_type in {StepType.WARMUP, StepType.COOLDOWN, StepType.RECOVERY}:
        return PhysiologicalIntent.RECOVERY
    # StepType.WORK — derive from session_type via map.
    return SESSION_INTENT_MAP[session_type]
