"""Unit tests for ContextBudgetService — pure estimation, no DB.

Covers the token-estimation formula and the budget-threshold mapping.
The assembly methods (build_first_message_context,
build_workout_context) require repositories and the real DB; they are
exercised in integration tests under tests/integration/.
"""

from __future__ import annotations

import json

from app.services.context_budget_service import (
    MAX_TOKENS,
    ContextBudgetService,
)


class TestEstimateTokens:
    def test_estimate_tokens_uses_json_length_over_four(self):
        obj = {"a": "b"}
        expected = (len(json.dumps(obj)) + 3) // 4
        assert ContextBudgetService.estimate_tokens(obj) == expected

    def test_estimate_tokens_zero_for_empty_dict(self):
        assert ContextBudgetService.estimate_tokens({}) == 1

    def test_estimate_tokens_scales_with_payload_size(self):
        small = ContextBudgetService.estimate_tokens({"a": "b"})
        big = ContextBudgetService.estimate_tokens({"a": "b" * 100})
        assert big > small

    def test_estimate_tokens_handles_nested_structures(self):
        nested = {"outer": {"inner": {"key": "value"}}}
        tokens = ContextBudgetService.estimate_tokens(nested)
        assert tokens > 0


class TestMaxTokensPerAgent:
    def test_first_message_max_is_5000(self):
        assert MAX_TOKENS["first_message"] == 5000

    def test_workout_generation_max_is_3000(self):
        assert MAX_TOKENS["workout_generation"] == 3000

    def test_post_workout_max_is_6000(self):
        assert MAX_TOKENS["post_workout"] == 6000

    def test_workout_budget_smaller_than_first_message_budget(self):
        # FirstMessage has more context (profile, goals, plan overview).
        # WorkoutGeneration has just the session + readiness digest.
        assert (
            MAX_TOKENS["workout_generation"] < MAX_TOKENS["first_message"]
        )


class TestContextSection:
    def test_context_section_carries_name_priority_budget(self):
        from app.services.context_budget_service import ContextSection

        section = ContextSection(
            name="readiness",
            priority_weight=90,
            token_budget=200,
        )
        assert section.name == "readiness"
        assert section.priority_weight == 90
        assert section.token_budget == 200

    def test_context_section_is_immutable(self):
        from app.services.context_budget_service import ContextSection

        section = ContextSection(name="x", priority_weight=1, token_budget=1)
        try:
            section.name = "y"  # type: ignore[misc]
        except Exception as exc:
            assert "frozen" in str(type(exc).__name__).lower() or "FrozenInstance" in str(
                type(exc)
            )
        else:
            raise AssertionError("ContextSection must be frozen")


class TestFirstMessageContextToDict:
    def test_to_dict_serialises_all_fields(self):
        from app.services.context_budget_service import (
            FirstBlockPreview,
            FirstMessageContext,
            GoalSummary,
            PlanOverview,
            ProfileSummary,
        )
        from app.models.enums import GoalType, SportBackground

        ctx = FirstMessageContext(
            profile_summary=ProfileSummary(
                sport_background=SportBackground.RUNNING_PRIMARY,
                years_structured_training=3,
                fitness_level=3,
                recent_injury=None,
            ),
            goal_summary=GoalSummary(
                goal_type=GoalType.RACE_EVENT,
                goal_event_type="marathon",
                goal_event_date="2026-12-06",
                weeks_to_event=20,
                goal_description=None,
            ),
            readiness_level="green",
            confidence_level="low",
            fitness_form_descriptor="ready to build",
            data_tier=3,
            computed_observations={
                "aerobic_base_assessment": "moderate aerobic base",
                "structural_risk_flag": False,
                "structural_risk_reason": None,
                "training_consistency_signal": "3 years of structured training",
            },
            plan_overview=PlanOverview(phases=[], total_weeks=24),
            first_block_preview=FirstBlockPreview(
                session_types_in_week_1=["easy_run"],
                session_types_in_week_2=["easy_run", "threshold"],
                primary_focus="building aerobic base",
            ),
        )

        d = ctx.to_dict()
        assert d["profile_summary"]["sport_background"] == "running_primary"
        assert d["goal_summary"]["goal_type"] == "race_event"
        assert d["readiness_level"] == "green"
        assert d["confidence_level"] == "low"
        assert d["data_tier"] == 3
        assert d["computed_observations"]["structural_risk_flag"] is False
        assert d["plan_overview"]["total_weeks"] == 24


class TestWorkoutGenerationContextToDict:
    def test_to_dict_serialises_all_fields(self):
        from app.services.context_budget_service import (
            WorkoutGenerationContext,
            WorkoutReadinessDigest,
            WorkoutSessionSummary,
        )

        ctx = WorkoutGenerationContext(
            session=WorkoutSessionSummary(
                session_type="threshold",
                phase_label="threshold",
                week_number=4,
                intent_description="Build threshold",
                approximate_duration_minutes=60,
            ),
            readiness=WorkoutReadinessDigest(
                recovery_modifier_level="green",
                recovery_modifier_reason=None,
                confidence_level="low",
                fitness_form_descriptor="ready to build",
                threshold_target_description="easy aerobic effort and comfortably hard intervals",
                lt2_pace_sec_per_km=None,
            ),
            data_tier=3,
            target_type="gap",
            relevant_objectives=[],
        )

        d = ctx.to_dict()
        assert d["session"]["session_type"] == "threshold"
        assert d["session"]["week_number"] == 4
        assert d["readiness"]["recovery_modifier_level"] == "green"
        assert d["data_tier"] == 3
        assert d["target_type"] == "gap"
        assert d["relevant_objectives"] == []


class TestBudgetEnforcement:
    def test_first_message_budget_is_5000(self):
        from app.services.context_budget_service import MAX_TOKENS

        assert MAX_TOKENS["first_message"] == 5000

    def test_workout_generation_budget_is_3000(self):
        from app.services.context_budget_service import MAX_TOKENS

        assert MAX_TOKENS["workout_generation"] == 3000