from app.models.enums import SessionType, TrainingPhase
from app.schemas.plan_generation import (
    PlanBlueprint,
    WeekPlan,
    SessionAssignment,
    PhaseArc,
    ValidationResult,
    ConstraintViolation,
)

# Weekday order for adjacency checking
WEEKDAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# Hard sessions that count against key session density
HIGH_STRESS_TYPES = {
    SessionType.THRESHOLD,
    SessionType.VO2MAX,
    SessionType.TEMPO,
    SessionType.RACE_SPECIFIC,
    SessionType.LONG_RUN,
    SessionType.MEDIUM_LONG_RUN,
    SessionType.HILL_REPEATS,
    SessionType.FARTLEK,
    SessionType.TEST_SESSION,
}

# Session types that are "easy" (allowed after long run or as recovery)
EASY_SESSION_TYPES = {
    SessionType.REST,
    SessionType.RECOVERY_RUN,
    SessionType.EASY_RUN,
    SessionType.STRIDES,
    SessionType.DRILLS_MOBILITY,
    SessionType.CROSS_TRAINING,
}

# Types that require an easy day after (long runs)
LONG_RUN_TYPES = {
    SessionType.LONG_RUN,
    SessionType.MEDIUM_LONG_RUN,
}


VALIDATOR_VERSION = "v1"


class PlanConstraintValidator:
    def validate(
        self,
        blueprint: PlanBlueprint,
        available_days: dict[str, dict],
        phase_arc: PhaseArc,
    ) -> ValidationResult:
        violations: list[ConstraintViolation] = []

        # Flatten all sessions chronologically for cross-week validation
        all_sessions = self._flatten_sessions(blueprint)

        # Validate week-level constraints
        for week_plan in blueprint.weeks:
            wv = self._validate_week(
                week_plan, available_days, phase_arc, all_sessions
            )
            violations.extend(wv)

        # Cross-week adjacency: long run must be followed by easy next day
        lr_violations = self._validate_long_run_recovery(all_sessions, available_days)
        violations.extend(lr_violations)

        return ValidationResult(
            is_valid=len(violations) == 0,
            violations=violations,
        )

    def _flatten_sessions(
        self, blueprint: PlanBlueprint
    ) -> list[tuple[int, str, SessionAssignment]]:
        """Flatten all sessions with (week_number, day, assignment)."""
        sessions = []
        for week in blueprint.weeks:
            for day, assignment in week.sessions.items():
                sessions.append((week.week_number, day, assignment))
        return sessions

    def _validate_week(
        self,
        week_plan: WeekPlan,
        available_days: dict[str, dict],
        phase_arc: PhaseArc,
        all_sessions: list[tuple[int, str, SessionAssignment]],
    ) -> list[ConstraintViolation]:
        violations: list[ConstraintViolation] = []

        # 1. Sessions only on available days
        for day in week_plan.sessions:
            if day not in available_days:
                violations.append(
                    ConstraintViolation(
                        rule="available_day_only",
                        week_number=week_plan.week_number,
                        day=day,
                        details=f"Session scheduled on non-available day '{day}'",
                    )
                )

        # 2. No duplicate sessions per day
        seen_days = set()
        for day in week_plan.sessions:
            if day in seen_days:
                violations.append(
                    ConstraintViolation(
                        rule="no_duplicate_sessions_per_day",
                        week_number=week_plan.week_number,
                        day=day,
                        details=f"Duplicate session for day '{day}'",
                    )
                )
            seen_days.add(day)

        # 3. Week structure aligns with phase arc
        phase_arc_phases = {p.phase: p for p in phase_arc.phases}
        week_phase = week_plan.phase
        if week_phase not in phase_arc_phases:
            violations.append(
                ConstraintViolation(
                    rule="phase_arc_alignment",
                    week_number=week_plan.week_number,
                    details=f"Week {week_plan.week_number} has phase '{week_phase.value}' which is not in the phase arc",
                )
            )

        # 4. No back-to-back threshold/VO2 sessions within a week
        sessions_ordered = [
            (day, week_plan.sessions[day])
            for day in WEEKDAY_ORDER
            if day in week_plan.sessions
        ]
        for i in range(len(sessions_ordered) - 1):
            curr_day, curr_session = sessions_ordered[i]
            next_day, next_session = sessions_ordered[i + 1]
            if (
                curr_session.session_type in {SessionType.THRESHOLD, SessionType.VO2MAX}
                and next_session.session_type
                in {SessionType.THRESHOLD, SessionType.VO2MAX}
            ):
                violations.append(
                    ConstraintViolation(
                        rule="no_back_to_back_intensity",
                        week_number=week_plan.week_number,
                        day=next_day,
                        details=f"Back-to-back intensity sessions: {curr_day} and {next_day}",
                    )
                )

        # 5. Max two key sessions per week
        key_sessions = [
            day for day, session in week_plan.sessions.items()
            if session.is_key_session
        ]
        if len(key_sessions) > 2:
            violations.append(
                ConstraintViolation(
                    rule="max_two_key_sessions",
                    week_number=week_plan.week_number,
                    details=f"Too many key sessions ({len(key_sessions)}): {key_sessions}",
                )
            )

        # 6. Recovery week reduced density
        if week_plan.week_number in phase_arc.recovery_weeks:
            hard_count = sum(
                1
                for day, session in week_plan.sessions.items()
                if session.session_type in HIGH_STRESS_TYPES
            )
            if hard_count > 2:
                violations.append(
                    ConstraintViolation(
                        rule="recovery_week_density",
                        week_number=week_plan.week_number,
                        details=f"Recovery week has {hard_count} hard sessions (max 2 allowed)",
                    )
                )

        return violations

    def _validate_long_run_recovery(
        self,
        all_sessions: list[tuple[int, str, SessionAssignment]],
        available_days: dict[str, dict],
    ) -> list[ConstraintViolation]:
        violations: list[ConstraintViolation] = []
        # Build ordered list of (week, day, assignment)
        ordered = sorted(
            all_sessions,
            key=lambda x: (x[0], WEEKDAY_ORDER.index(x[1]) if x[1] in WEEKDAY_ORDER else 7),
        )

        for i, (week_num, day, session) in enumerate(ordered):
            if session.session_type not in LONG_RUN_TYPES:
                continue
            # Find next scheduled session
            next_session = None
            for j in range(i + 1, len(ordered)):
                next_session = ordered[j]
                break
            if next_session is None:
                continue  # No next day — fine, plan may end with long run
            next_day, next_assign = next_session[1], next_session[2]
            if next_assign.session_type not in EASY_SESSION_TYPES:
                violations.append(
                    ConstraintViolation(
                        rule="long_run_recovery",
                        week_number=week_num,
                        day=day,
                        details=f"Long run on {day} is not followed by easy recovery session; next session is {next_assign.session_type.value}",
                    )
                )
        return violations