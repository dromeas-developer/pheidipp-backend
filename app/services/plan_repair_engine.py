import logging
from app.models.enums import SessionType
from app.schemas.plan_generation import (
    PlanBlueprint,
    WeekPlan,
    SessionAssignment,
    ValidationResult,
)

logger = logging.getLogger(__name__)

MAX_REPAIR_ATTEMPTS = 1

# Downgrade map for back-to-back intensity repairs
INTENSITY_DOWNGRADE = {
    SessionType.THRESHOLD: SessionType.EASY_RUN,
    SessionType.VO2MAX: SessionType.EASY_RUN,
    SessionType.TEMPO: SessionType.EASY_RUN,
}


class PlanRepairEngine:
    def repair(
        self,
        blueprint: PlanBlueprint,
        validation_result: ValidationResult,
        available_days: dict[str, dict],
    ) -> PlanBlueprint:
        if validation_result.is_valid:
            return blueprint

        repairs_made = 0
        current_blueprint = blueprint

        for violation in validation_result.violations:
            if repairs_made >= MAX_REPAIR_ATTEMPTS:
                break

            repaired = self._repair_violation(
                current_blueprint, violation, available_days
            )
            if repaired is not None:
                current_blueprint = repaired
                repairs_made += 1
                logger.info(
                    f"Repair applied: rule={violation.rule}, "
                    f"week={violation.week_number}, day={violation.day}"
                )

        return current_blueprint

    def _repair_violation(
        self,
        blueprint: PlanBlueprint,
        violation,
        available_days: dict[str, dict],
    ) -> PlanBlueprint | None:
        rule = violation.rule

        if rule == "available_day_only":
            return self._remove_session_on_invalid_day(blueprint, violation)

        if rule == "no_back_to_back_intensity":
            return self._downgrade_back_to_back(blueprint, violation)

        if rule == "long_run_recovery":
            return self._insert_recovery_after_long_run(blueprint, violation)

        if rule == "max_two_key_sessions":
            return self._remove_excess_key_sessions(blueprint, violation)

        return None

    def _remove_session_on_invalid_day(
        self, blueprint: PlanBlueprint, violation
    ) -> PlanBlueprint | None:
        week_number = violation.week_number
        day = violation.day

        for week in blueprint.weeks:
            if week.week_number == week_number and day in week.sessions:
                new_sessions = {k: v for k, v in week.sessions.items() if k != day}
                week.sessions.clear()
                week.sessions.update(new_sessions)
                return blueprint
        return blueprint

    def _downgrade_back_to_back(
        self, blueprint: PlanBlueprint, violation
    ) -> PlanBlueprint | None:
        week_number = violation.week_number
        day = violation.day

        for week in blueprint.weeks:
            if week.week_number == week_number and day in week.sessions:
                current = week.sessions[day]
                new_type = INTENSITY_DOWNGRADE.get(current.session_type)
                if new_type:
                    week.sessions[day] = SessionAssignment(
                        session_type=new_type,
                        target_duration_minutes=current.target_duration_minutes,
                        is_key_session=False,
                    )
                return blueprint
        return blueprint

    def _insert_recovery_after_long_run(
        self, blueprint: PlanBlueprint, violation
    ) -> PlanBlueprint | None:
        return None  # Cannot insert sessions without topology redesign

    def _remove_excess_key_sessions(
        self, blueprint: PlanBlueprint, violation
    ) -> PlanBlueprint | None:
        week_number = violation.week_number

        for week in blueprint.weeks:
            if week.week_number == week_number:
                key_days = [
                    day
                    for day, session in week.sessions.items()
                    if session.is_key_session
                ]
                # Remove key flag from excess ones (keep first 2)
                for i, day in enumerate(key_days):
                    if i >= 2:
                        current = week.sessions[day]
                        week.sessions[day] = SessionAssignment(
                            session_type=current.session_type,
                            target_duration_minutes=current.target_duration_minutes,
                            is_key_session=False,
                        )
                return blueprint
        return blueprint