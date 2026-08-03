"""Unit tests for WorkoutGenerationAgent — pure logic, no LLM, no DB.

Covers the static helpers (coercion, intent derivation, target-type
selection) and the proxy routing per ADR-007.
"""

from __future__ import annotations

import re
from typing import Any

from app.agents.workout_generation_agent import (
    WorkoutGenerationAgent,
    _coerce_int,
    _coerce_int_range,
    _NON_NULL_NUMERIC_FIELDS_BY_TARGET_TYPE,
)
from app.models.enums import (
    DataTier,
    PhysiologicalIntent,
    SessionType,
    StepType,
)
from app.services.context_budget_service import WorkoutGenerationContext
from app.services.workout_generation_errors import WorkoutGenerationContractError
from app.services.workout_target_types import (
    DATA_TIER_TARGET_TYPE,
    SESSION_INTENT_MAP,
    get_step_physiological_intent,
)


class TestCoerceInt:
    def test_none_returns_none(self):
        assert _coerce_int(None) is None

    def test_int_returns_int(self):
        assert _coerce_int(42) == 42

    def test_negative_int_returns_int(self):
        assert _coerce_int(-7) == -7

    def test_float_truncated_to_int(self):
        assert _coerce_int(900.0) == 900

    def test_bool_returns_int(self):
        assert _coerce_int(True) == 1
        assert _coerce_int(False) == 0

    def test_empty_string_returns_none(self):
        assert _coerce_int("") is None

    def test_whitespace_string_returns_none(self):
        assert _coerce_int("   ") is None

    def test_numeric_string_returns_int(self):
        assert _coerce_int("42") == 42
        assert _coerce_int("42.7") == 42

    def test_unparseable_string_returns_none(self):
        assert _coerce_int("not-a-number") is None


class TestCoerceIntRange:
    def test_none_returns_min_max_none(self):
        assert _coerce_int_range(None) == {"min": None, "max": None}

    def test_flat_numeric_treated_as_max(self):
        assert _coerce_int_range(300) == {"min": None, "max": 300}

    def test_dict_with_min_max(self):
        assert _coerce_int_range({"min": 280, "max": 320}) == {"min": 280, "max": 320}

    def test_dict_with_nulls(self):
        assert _coerce_int_range({"min": None, "max": None}) == {
            "min": None,
            "max": None,
        }

    def test_unparseable_returns_none_pair(self):
        assert _coerce_int_range("not-a-dict") == {"min": None, "max": None}


class TestNonNullNumericFieldsByTargetType:
    def test_power_target_type_allows_only_power_watts(self):
        assert _NON_NULL_NUMERIC_FIELDS_BY_TARGET_TYPE["power"] == {
            "target_power_watts"
        }

    def test_gap_target_type_allows_only_gap(self):
        assert _NON_NULL_NUMERIC_FIELDS_BY_TARGET_TYPE["gap"] == {
            "target_gap_sec_per_km"
        }

    def test_description_target_type_allows_no_numerics(self):
        assert _NON_NULL_NUMERIC_FIELDS_BY_TARGET_TYPE["description"] == set()


class TestDataTierTargetType:
    def test_tier_1_maps_to_power(self):
        assert DATA_TIER_TARGET_TYPE[DataTier.TIER_1] == "power"

    def test_tier_2_maps_to_power(self):
        assert DATA_TIER_TARGET_TYPE[DataTier.TIER_2] == "power"

    def test_tier_3_maps_to_gap(self):
        assert DATA_TIER_TARGET_TYPE[DataTier.TIER_3] == "gap"

    def test_tier_4_maps_to_gap(self):
        assert DATA_TIER_TARGET_TYPE[DataTier.TIER_4] == "gap"

    def test_tier_5_maps_to_description(self):
        assert DATA_TIER_TARGET_TYPE[DataTier.TIER_5] == "description"

    def test_tier_6_maps_to_description(self):
        assert DATA_TIER_TARGET_TYPE[DataTier.TIER_6] == "description"


class TestSessionIntentMap:
    def test_rest_maps_to_recovery(self):
        assert SESSION_INTENT_MAP[SessionType.REST] == PhysiologicalIntent.RECOVERY

    def test_recovery_run_maps_to_recovery(self):
        assert (
            SESSION_INTENT_MAP[SessionType.RECOVERY_RUN]
            == PhysiologicalIntent.RECOVERY
        )

    def test_easy_run_maps_to_low_aerobic(self):
        assert (
            SESSION_INTENT_MAP[SessionType.EASY_RUN]
            == PhysiologicalIntent.LOW_AEROBIC
        )

    def test_long_run_maps_to_high_aerobic(self):
        assert (
            SESSION_INTENT_MAP[SessionType.LONG_RUN]
            == PhysiologicalIntent.HIGH_AEROBIC
        )

    def test_threshold_maps_to_threshold(self):
        assert (
            SESSION_INTENT_MAP[SessionType.THRESHOLD] == PhysiologicalIntent.THRESHOLD
        )

    def test_vo2max_maps_to_vo2max(self):
        assert SESSION_INTENT_MAP[SessionType.VO2MAX] == PhysiologicalIntent.VO2MAX

    def test_test_session_maps_to_vo2max(self):
        assert (
            SESSION_INTENT_MAP[SessionType.TEST_SESSION] == PhysiologicalIntent.VO2MAX
        )


class TestGetStepPhysiologicalIntent:
    def test_warmup_step_returns_recovery_for_any_session(self):
        for session_type in (
            SessionType.EASY_RUN,
            SessionType.THRESHOLD,
            SessionType.LONG_RUN,
        ):
            assert (
                get_step_physiological_intent(StepType.WARMUP, session_type)
                == PhysiologicalIntent.RECOVERY
            )

    def test_cooldown_step_returns_recovery_for_any_session(self):
        for session_type in (
            SessionType.EASY_RUN,
            SessionType.THRESHOLD,
            SessionType.LONG_RUN,
        ):
            assert (
                get_step_physiological_intent(StepType.COOLDOWN, session_type)
                == PhysiologicalIntent.RECOVERY
            )

    def test_recovery_step_returns_recovery(self):
        assert (
            get_step_physiological_intent(StepType.RECOVERY, SessionType.EASY_RUN)
            == PhysiologicalIntent.RECOVERY
        )

    def test_work_step_easy_run_returns_low_aerobic(self):
        assert (
            get_step_physiological_intent(StepType.WORK, SessionType.EASY_RUN)
            == PhysiologicalIntent.LOW_AEROBIC
        )

    def test_work_step_threshold_returns_threshold(self):
        assert (
            get_step_physiological_intent(StepType.WORK, SessionType.THRESHOLD)
            == PhysiologicalIntent.THRESHOLD
        )

    def test_work_step_long_run_returns_high_aerobic(self):
        assert (
            get_step_physiological_intent(StepType.WORK, SessionType.LONG_RUN)
            == PhysiologicalIntent.HIGH_AEROBIC
        )


class TestParseAndValidateOutput:
    def _make_context(self, target_type: str = "gap") -> WorkoutGenerationContext:
        return WorkoutGenerationContext(
            session=None,
            readiness=None,
            data_tier=3,
            target_type=target_type,
            relevant_objectives=[],
        )

    def _make_planned_session_stub(self, session_type: SessionType) -> Any:
        class _Stub:
            session_type: SessionType

        stub = _Stub()
        stub.session_type = session_type
        return stub

    def _build_agent(self) -> WorkoutGenerationAgent:
        return WorkoutGenerationAgent.__new__(WorkoutGenerationAgent)

    def _threshold_payload(self) -> str:
        import json

        return json.dumps(
            {
                "steps": [
                    {
                        "step_order": 1,
                        "step_type": "warmup",
                        "physiological_intent": "recovery",
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": None,
                        "description": "Easy warmup",
                    },
                    {
                        "step_order": 2,
                        "step_type": "work",
                        "physiological_intent": "threshold",
                        "target_duration_seconds": 300,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": {"min": 240, "max": 250},
                        "description": "Threshold rep 1",
                    },
                    {
                        "step_order": 3,
                        "step_type": "cooldown",
                        "physiological_intent": "recovery",
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": None,
                        "description": "Easy cooldown",
                    },
                ]
            }
        )

    async def test_threshold_session_produces_warmup_work_cooldown_sequence(self):
        agent = self._build_agent()
        context = self._make_context(target_type="gap")
        planned_session = self._make_planned_session_stub(SessionType.THRESHOLD)

        parsed = agent._parse_and_validate_output(
            generated_content=self._threshold_payload(),
            planned_session=planned_session,
            context=context,
        )

        assert [s["step_type"] for s in parsed] == [
            StepType.WARMUP,
            StepType.WORK,
            StepType.COOLDOWN,
        ]
        assert [s["step_order"] for s in parsed] == [1, 2, 3]

    async def test_step_orders_strictly_sequential_one_indexed(self):
        agent = self._build_agent()
        context = self._make_context()
        planned_session = self._make_planned_session_stub(SessionType.EASY_RUN)

        import json

        payload = json.dumps(
            {
                "steps": [
                    {
                        "step_order": 1,
                        "step_type": "warmup",
                        "physiological_intent": "recovery",
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": None,
                        "description": "Warmup",
                    },
                    {
                        "step_order": 2,
                        "step_type": "cooldown",
                        "physiological_intent": "recovery",
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": None,
                        "description": "Cooldown",
                    },
                ]
            }
        )

        parsed = agent._parse_and_validate_output(
            generated_content=payload,
            planned_session=planned_session,
            context=context,
        )
        assert [s["step_order"] for s in parsed] == [1, 2]

    async def test_step_orders_must_be_contiguous_raises_contract_error(self):
        agent = self._build_agent()
        context = self._make_context()
        planned_session = self._make_planned_session_stub(SessionType.EASY_RUN)

        import json

        payload = json.dumps(
            {
                "steps": [
                    {
                        "step_order": 1,
                        "step_type": "warmup",
                        "physiological_intent": "recovery",
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": None,
                        "description": "Warmup",
                    },
                    {
                        "step_order": 3,
                        "step_type": "cooldown",
                        "physiological_intent": "recovery",
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": None,
                        "description": "Cooldown",
                    },
                ]
            }
        )

        try:
            agent._parse_and_validate_output(
                generated_content=payload,
                planned_session=planned_session,
                context=context,
            )
        except WorkoutGenerationContractError as exc:
            assert "expected 2" in str(exc)
        else:
            raise AssertionError("WorkoutGenerationContractError not raised")

    async def test_first_step_must_be_warmup_raises_contract_error(self):
        agent = self._build_agent()
        context = self._make_context()
        planned_session = self._make_planned_session_stub(SessionType.EASY_RUN)

        import json

        payload = json.dumps(
            {
                "steps": [
                    {
                        "step_order": 1,
                        "step_type": "work",
                        "physiological_intent": "low_aerobic",
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": {"min": 360, "max": 380},
                        "description": "Easy continuous",
                    },
                    {
                        "step_order": 2,
                        "step_type": "cooldown",
                        "physiological_intent": "recovery",
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": None,
                        "description": "Cooldown",
                    },
                ]
            }
        )

        try:
            agent._parse_and_validate_output(
                generated_content=payload,
                planned_session=planned_session,
                context=context,
            )
        except WorkoutGenerationContractError as exc:
            assert "first step must be warmup" in str(exc)
        else:
            raise AssertionError("WorkoutGenerationContractError not raised")

    async def test_last_step_must_be_cooldown_raises_contract_error(self):
        agent = self._build_agent()
        context = self._make_context()
        planned_session = self._make_planned_session_stub(SessionType.EASY_RUN)

        import json

        payload = json.dumps(
            {
                "steps": [
                    {
                        "step_order": 1,
                        "step_type": "warmup",
                        "physiological_intent": "recovery",
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": None,
                        "description": "Warmup",
                    },
                    {
                        "step_order": 2,
                        "step_type": "work",
                        "physiological_intent": "low_aerobic",
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": {"min": 360, "max": 380},
                        "description": "Easy continuous",
                    },
                ]
            }
        )

        try:
            agent._parse_and_validate_output(
                generated_content=payload,
                planned_session=planned_session,
                context=context,
            )
        except WorkoutGenerationContractError as exc:
            assert "last step must be cooldown" in str(exc)
        else:
            raise AssertionError("WorkoutGenerationContractError not raised")

    async def test_work_intent_must_match_session_intent_map_raises_contract_error(
        self,
    ):
        agent = self._build_agent()
        context = self._make_context()
        planned_session = self._make_planned_session_stub(SessionType.EASY_RUN)

        import json

        payload = json.dumps(
            {
                "steps": [
                    {
                        "step_order": 1,
                        "step_type": "warmup",
                        "physiological_intent": "recovery",
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": None,
                        "description": "Warmup",
                    },
                    {
                        "step_order": 2,
                        "step_type": "work",
                        "physiological_intent": "threshold",
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": {"min": 240, "max": 250},
                        "description": "Wrong intent for easy run",
                    },
                    {
                        "step_order": 3,
                        "step_type": "cooldown",
                        "physiological_intent": "recovery",
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": None,
                        "description": "Cooldown",
                    },
                ]
            }
        )

        try:
            agent._parse_and_validate_output(
                generated_content=payload,
                planned_session=planned_session,
                context=context,
            )
        except WorkoutGenerationContractError as exc:
            assert "contradicts" in str(exc)
        else:
            raise AssertionError("WorkoutGenerationContractError not raised")

    async def test_power_target_type_rejects_gap_field_populated_raises_contract_error(
        self,
    ):
        agent = self._build_agent()
        context = self._make_context(target_type="power")
        planned_session = self._make_planned_session_stub(SessionType.EASY_RUN)

        import json

        payload = json.dumps(
            {
                "steps": [
                    {
                        "step_order": 1,
                        "step_type": "warmup",
                        "physiological_intent": "recovery",
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": None,
                        "description": "Warmup",
                    },
                    {
                        "step_order": 2,
                        "step_type": "work",
                        "physiological_intent": "low_aerobic",
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": {"min": 200, "max": 220},
                        "target_gap_sec_per_km": {"min": 360, "max": 380},
                        "description": "Power and gap both populated",
                    },
                    {
                        "step_order": 3,
                        "step_type": "cooldown",
                        "physiological_intent": "recovery",
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": None,
                        "description": "Cooldown",
                    },
                ]
            }
        )

        try:
            agent._parse_and_validate_output(
                generated_content=payload,
                planned_session=planned_session,
                context=context,
            )
        except WorkoutGenerationContractError as exc:
            assert "forbids it" in str(exc)
        else:
            raise AssertionError("WorkoutGenerationContractError not raised")

    async def test_power_target_type_requires_power_field_raises_contract_error(
        self,
    ):
        agent = self._build_agent()
        context = self._make_context(target_type="power")
        planned_session = self._make_planned_session_stub(SessionType.EASY_RUN)

        import json

        payload = json.dumps(
            {
                "steps": [
                    {
                        "step_order": 1,
                        "step_type": "warmup",
                        "physiological_intent": "recovery",
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": None,
                        "description": "Warmup",
                    },
                    {
                        "step_order": 2,
                        "step_type": "work",
                        "physiological_intent": "low_aerobic",
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": None,
                        "description": "No numeric on power tier",
                    },
                    {
                        "step_order": 3,
                        "step_type": "cooldown",
                        "physiological_intent": "recovery",
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": None,
                        "description": "Cooldown",
                    },
                ]
            }
        )

        try:
            agent._parse_and_validate_output(
                generated_content=payload,
                planned_session=planned_session,
                context=context,
            )
        except WorkoutGenerationContractError as exc:
            assert "requires target_power_watts" in str(exc)
        else:
            raise AssertionError("WorkoutGenerationContractError not raised")

    async def test_description_target_type_accepts_no_numeric_fields(self):
        agent = self._build_agent()
        context = self._make_context(target_type="description")
        planned_session = self._make_planned_session_stub(SessionType.EASY_RUN)

        import json

        payload = json.dumps(
            {
                "steps": [
                    {
                        "step_order": 1,
                        "step_type": "warmup",
                        "physiological_intent": "recovery",
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": None,
                        "description": "Easy warmup",
                    },
                    {
                        "step_order": 2,
                        "step_type": "work",
                        "physiological_intent": "low_aerobic",
                        "target_duration_seconds": 1800,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": None,
                        "description": "Easy continuous effort",
                    },
                    {
                        "step_order": 3,
                        "step_type": "cooldown",
                        "physiological_intent": "recovery",
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": None,
                        "description": "Easy cooldown",
                    },
                ]
            }
        )

        parsed = agent._parse_and_validate_output(
            generated_content=payload,
            planned_session=planned_session,
            context=context,
        )
        assert len(parsed) == 3

    async def test_empty_description_raises_contract_error(self):
        agent = self._build_agent()
        context = self._make_context()
        planned_session = self._make_planned_session_stub(SessionType.EASY_RUN)

        import json

        payload = json.dumps(
            {
                "steps": [
                    {
                        "step_order": 1,
                        "step_type": "warmup",
                        "physiological_intent": "recovery",
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": None,
                        "description": "   ",
                    },
                    {
                        "step_order": 2,
                        "step_type": "cooldown",
                        "physiological_intent": "recovery",
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": None,
                        "description": "Cooldown",
                    },
                ]
            }
        )

        try:
            agent._parse_and_validate_output(
                generated_content=payload,
                planned_session=planned_session,
                context=context,
            )
        except WorkoutGenerationContractError as exc:
            assert "description must be a non-empty string" in str(exc)
        else:
            raise AssertionError("WorkoutGenerationContractError not raised")

    async def test_null_physiological_intent_raises_contract_error(self):
        agent = self._build_agent()
        context = self._make_context()
        planned_session = self._make_planned_session_stub(SessionType.EASY_RUN)

        import json

        payload = json.dumps(
            {
                "steps": [
                    {
                        "step_order": 1,
                        "step_type": "warmup",
                        "physiological_intent": None,
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": None,
                        "description": "Warmup",
                    },
                    {
                        "step_order": 2,
                        "step_type": "cooldown",
                        "physiological_intent": "recovery",
                        "target_duration_seconds": 600,
                        "target_hr_zone": None,
                        "target_power_watts": None,
                        "target_gap_sec_per_km": None,
                        "description": "Cooldown",
                    },
                ]
            }
        )

        try:
            agent._parse_and_validate_output(
                generated_content=payload,
                planned_session=planned_session,
                context=context,
            )
        except WorkoutGenerationContractError as exc:
            assert "null physiological_intent" in str(exc)
        else:
            raise AssertionError("WorkoutGenerationContractError not raised")

    async def test_empty_json_raises_contract_error(self):
        agent = self._build_agent()
        context = self._make_context()
        planned_session = self._make_planned_session_stub(SessionType.EASY_RUN)

        try:
            agent._parse_and_validate_output(
                generated_content="",
                planned_session=planned_session,
                context=context,
            )
        except WorkoutGenerationContractError as exc:
            assert "empty output" in str(exc)
        else:
            raise AssertionError("WorkoutGenerationContractError not raised")

    async def test_invalid_json_raises_contract_error(self):
        agent = self._build_agent()
        context = self._make_context()
        planned_session = self._make_planned_session_stub(SessionType.EASY_RUN)

        try:
            agent._parse_and_validate_output(
                generated_content="not-json-at-all",
                planned_session=planned_session,
                context=context,
            )
        except WorkoutGenerationContractError as exc:
            assert "valid JSON" in str(exc)
        else:
            raise AssertionError("WorkoutGenerationContractError not raised")

    async def test_no_steps_array_raises_contract_error(self):
        agent = self._build_agent()
        context = self._make_context()
        planned_session = self._make_planned_session_stub(SessionType.EASY_RUN)

        import json

        try:
            agent._parse_and_validate_output(
                generated_content=json.dumps({"foo": "bar"}),
                planned_session=planned_session,
                context=context,
            )
        except WorkoutGenerationContractError as exc:
            assert "steps" in str(exc)
        else:
            raise AssertionError("WorkoutGenerationContractError not raised")

    async def test_session_purpose_default_is_general_for_non_test_sessions(self):
        agent = self._build_agent()
        context = self._make_context()
        planned_session = self._make_planned_session_stub(SessionType.EASY_RUN)

        parsed = agent._parse_and_validate_output(
            generated_content=self._threshold_payload(),
            planned_session=planned_session,
            context=context,
        )
        assert all(s["session_purpose"] == "general" for s in parsed)

    async def test_session_purpose_is_calibration_for_test_session(self):
        agent = self._build_agent()
        context = self._make_context()
        planned_session = self._make_planned_session_stub(SessionType.TEST_SESSION)

        parsed = agent._parse_and_validate_output(
            generated_content=self._threshold_payload(),
            planned_session=planned_session,
            context=context,
        )
        assert all(s["session_purpose"] == "calibration" for s in parsed)


class TestBuildStepTarget:
    def _build_agent(self) -> WorkoutGenerationAgent:
        return WorkoutGenerationAgent.__new__(WorkoutGenerationAgent)

    def test_power_target_type_emits_watts_signal(self):
        agent = self._build_agent()
        target = agent._build_step_target(
            step_type=StepType.WORK,
            step_order=2,
            target_type="power",
            target_power_watts={"min": 280, "max": 320},
            target_gap_sec_per_km=None,
            target_hr_zone=None,
            description="Threshold rep",
        )
        assert target["signal_type"] == "power"
        assert target["primary"] == {"min": 280, "max": 320, "unit": "watts"}
        assert target["fallback"] is None

    def test_gap_target_type_emits_sec_per_km_signal(self):
        agent = self._build_agent()
        target = agent._build_step_target(
            step_type=StepType.WORK,
            step_order=2,
            target_type="gap",
            target_power_watts=None,
            target_gap_sec_per_km={"min": 240, "max": 250},
            target_hr_zone=None,
            description="Threshold rep",
        )
        assert target["signal_type"] == "gap"
        assert target["primary"] == {"min": 240, "max": 250, "unit": "sec_per_km"}

    def test_description_target_type_emits_no_primary(self):
        agent = self._build_agent()
        target = agent._build_step_target(
            step_type=StepType.WORK,
            step_order=2,
            target_type="description",
            target_power_watts=None,
            target_gap_sec_per_km=None,
            target_hr_zone=None,
            description="Easy effort by feel",
        )
        assert target["signal_type"] == "description"
        assert target["primary"] is None

    def test_unit_is_always_sec_per_km_for_gap(self):
        agent = self._build_agent()
        target = agent._build_step_target(
            step_type=StepType.WORK,
            step_order=2,
            target_type="gap",
            target_power_watts=None,
            target_gap_sec_per_km=300,
            target_hr_zone=None,
            description="Easy continuous",
        )
        assert target["primary"]["unit"] == "sec_per_km"


class TestBuildTargetSet:
    def _build_agent(self) -> WorkoutGenerationAgent:
        return WorkoutGenerationAgent.__new__(WorkoutGenerationAgent)

    def test_target_set_includes_all_step_targets(self):
        agent = self._build_agent()
        parsed_steps = [
            {
                "step_type": StepType.WARMUP,
                "target": {"signal_type": "description", "primary": None},
            },
            {
                "step_type": StepType.WORK,
                "target": {"signal_type": "gap", "primary": {"min": 240, "max": 250}},
            },
            {
                "step_type": StepType.COOLDOWN,
                "target": {"signal_type": "description", "primary": None},
            },
        ]
        target_set = agent._build_target_set(parsed_steps)
        assert len(target_set["targets"]) == 3
        assert "3 steps total" in target_set["description"]

    def test_target_set_description_counts_work_segments(self):
        agent = self._build_agent()
        parsed_steps = [
            {
                "step_type": StepType.WARMUP,
                "target": {"signal_type": "description", "primary": None},
            },
            {
                "step_type": StepType.WORK,
                "target": {"signal_type": "gap", "primary": {"min": 240, "max": 250}},
            },
            {
                "step_type": StepType.RECOVERY,
                "target": {"signal_type": "description", "primary": None},
            },
            {
                "step_type": StepType.WORK,
                "target": {"signal_type": "gap", "primary": {"min": 240, "max": 250}},
            },
            {
                "step_type": StepType.COOLDOWN,
                "target": {"signal_type": "description", "primary": None},
            },
        ]
        target_set = agent._build_target_set(parsed_steps)
        assert "5 steps total" in target_set["description"]
        assert "2 work segments" in target_set["description"]

    def test_target_set_description_uses_singular_for_single_work_segment(self):
        agent = self._build_agent()
        parsed_steps = [
            {
                "step_type": StepType.WARMUP,
                "target": {"signal_type": "description", "primary": None},
            },
            {
                "step_type": StepType.WORK,
                "target": {"signal_type": "gap", "primary": {"min": 240, "max": 250}},
            },
            {
                "step_type": StepType.COOLDOWN,
                "target": {"signal_type": "description", "primary": None},
            },
        ]
        target_set = agent._build_target_set(parsed_steps)
        assert "1 work segment." in target_set["description"]


class TestProxyRouting:
    def test_build_llm_client_returns_async_openai_with_proxy_base_url(self):
        from openai import AsyncOpenAI

        from app.config import settings

        instance = WorkoutGenerationAgent.__new__(WorkoutGenerationAgent)
        client = instance._build_llm_client()

        assert isinstance(client, AsyncOpenAI)
        assert client.base_url == settings.LITELLM_BASE_URL
        assert client.api_key == settings.LITELLM_API_KEY

    def test_no_direct_provider_sdk_imports(self):
        import app.agents.workout_generation_agent as module

        source = open(module.__file__).read()
        forbidden_imports = [
            r"^\s*import anthropic\b",
            r"^\s*from anthropic\b",
            r"^\s*import cohere\b",
            r"^\s*from cohere\b",
        ]
        for pattern in forbidden_imports:
            match = re.search(pattern, source, flags=re.MULTILINE)
            assert match is None, (
                f"Forbidden direct provider SDK import found: {match.group(0)}"
            )


class TestAgentName:
    def test_agent_name_is_class_name(self):
        assert WorkoutGenerationAgent.AGENT_NAME == "WorkoutGenerationAgent"

    def test_prompt_version_is_v1(self):
        assert WorkoutGenerationAgent.PROMPT_VERSION == "v1"