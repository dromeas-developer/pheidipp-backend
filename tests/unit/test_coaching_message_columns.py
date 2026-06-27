"""Unit tests for the ``CoachingMessage`` declarative surface (no DB).

Phase-1.2c introduces the ``CoachingMessage`` schema — an immutable
LLM-generated message to the athlete. Always linked to the active
``TwinState`` at generation time so every message can be traced back
to the twin-snapshot context.

Invariants pinned here:

* Immutable after creation — the model exposes no ``update()`` /
  ``delete()`` helpers; the future repository (Phase 1.5) restricts
  to ``insert()`` only.
* ``first_message`` — only one per athlete (partial unique index).
* ``post_workout`` — only one per ``activity_id`` (partial unique
  index).
* ``content`` is non-empty (CHECK constraint).
* ``activity_id`` is NULL for every ``message_type`` other than
  ``post_workout``.

Reference plan: docs/implementation/phase-1/phase-1-2c-p1-twin-fitness-coaching-workouts.md
Architecture: docs/architecture/01-entities/coaching-message.md
"""

from __future__ import annotations

import pytest
from sqlalchemy import (
    DateTime,
    String,
    Text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.models.coaching_message import CoachingMessage
from app.models.enums import MessageType
from tests.utils.model_helpers import (
    get_columns,
    get_indexes,
    get_check_constraints,
    get_check_text,
    get_foreign_keys_referencing,
    get_enum_values,
)


# ---------------------------------------------------------------------------
# Column presence and type.
# ---------------------------------------------------------------------------


class TestCoachingMessageRequiredColumns:
    def test_id_column_uuid_primary_key(self) -> None:
        col = get_columns(CoachingMessage)["id"]
        assert col.primary_key is True
        assert isinstance(col.type, PG_UUID)

    def test_athlete_id_required_uuid(self) -> None:
        col = get_columns(CoachingMessage)["athlete_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)

    def test_athlete_id_cascade_fk_to_athletes(self) -> None:
        """Athlete FK ON DELETE CASCADE — messages are wiped when
        the athlete account is deleted."""
        fks = get_foreign_keys_referencing(CoachingMessage, "athlete_id")
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "athletes"
        assert fk.ondelete == "CASCADE"

    def test_twin_state_id_required_uuid(self) -> None:
        """``twin_state_id`` is NOT NULL — every message is linked
        to the active TwinState at generation time."""
        col = get_columns(CoachingMessage)["twin_state_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)

    def test_twin_state_id_cascade_fk_to_twin_states(self) -> None:
        """TwinState FK ON DELETE CASCADE — messages are wiped when
        the parent TwinState is removed (history outlives only via
        the twin-state cascade)."""
        fks = get_foreign_keys_referencing(CoachingMessage, "twin_state_id")
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "twin_states"
        assert fk.ondelete == "CASCADE"

    def test_activity_id_nullable_uuid(self) -> None:
        """``activity_id`` is NULL for every MessageType other than
        ``post_workout`` — the column is nullable at the schema
        level and the partial unique index on
        ``post_workout + activity_id IS NOT NULL`` enforces the
        1:1 contract only for that type."""
        col = get_columns(CoachingMessage)["activity_id"]
        assert col.nullable is True
        assert isinstance(col.type, PG_UUID)

    def test_activity_id_set_null_fk_to_activities(self) -> None:
        """Activity FK ON DELETE SET NULL — message history is
        preserved when an Activity is deleted (the activity_id
        reference is nulled out)."""
        fks = get_foreign_keys_referencing(CoachingMessage, "activity_id")
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "activities"
        assert fk.ondelete == "SET NULL"

    def test_message_type_required_enum(self) -> None:
        col = get_columns(CoachingMessage)["message_type"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        actual = sorted(get_enum_values(col, MessageType))
        expected = sorted(
            [
                "confidence_upgrade",
                "cycle_check_in",
                "first_message",
                "phase_transition",
                "plan_regeneration",
                "post_workout",
                "weekly_summary",
                "wellness_alert",
            ]
        )
        assert actual == expected

    def test_content_required_text(self) -> None:
        col = get_columns(CoachingMessage)["content"]
        assert col.nullable is False
        assert isinstance(col.type, Text)

    def test_prompt_version_required_string(self) -> None:
        col = get_columns(CoachingMessage)["prompt_version"]
        assert col.nullable is False
        assert isinstance(col.type, String)
        assert col.type.length == 32

    def test_generated_at_required_datetime(self) -> None:
        col = get_columns(CoachingMessage)["generated_at"]
        assert col.nullable is False
        assert isinstance(col.type, DateTime)


# ---------------------------------------------------------------------------
# Partial unique indexes — first_message and post_workout.
# ---------------------------------------------------------------------------


class TestCoachingMessageFirstMessagePartialUniqueIndex:
    """``first_message`` has at most one active message per athlete —
    DB-enforced via partial unique index
    ``uq_coaching_messages_athlete_first_message`` on ``(athlete_id)
    WHERE message_type = 'first_message'``."""

    def test_first_message_partial_unique_index_present(self) -> None:
        indexes = get_indexes(CoachingMessage)
        assert "uq_coaching_messages_athlete_first_message" in indexes, (
            "CoachingMessage must declare "
            "`uq_coaching_messages_athlete_first_message` to "
            "enforce one first_message per athlete."
        )

    def test_first_message_index_is_unique(self) -> None:
        idx = get_indexes(CoachingMessage)["uq_coaching_messages_athlete_first_message"]
        assert idx.unique is True

    def test_first_message_partial_predicate_present(self) -> None:
        idx = get_indexes(CoachingMessage)["uq_coaching_messages_athlete_first_message"]
        predicate = idx.dialect_options.get("postgresql", {}).get("where")
        assert predicate is not None, (
            "uq_coaching_messages_athlete_first_message must declare "
            "a postgresql_where predicate — without it the index "
            "would block multiple messages in any type per athlete."
        )
        rendered = str(predicate).lower()
        assert "message_type" in rendered and "first_message" in rendered, (
            "uq_coaching_messages_athlete_first_message partial "
            "predicate must constrain `message_type = 'first_message'`. "
            f"Got: {predicate!r}"
        )

    def test_first_message_index_columns(self) -> None:
        idx = get_indexes(CoachingMessage)["uq_coaching_messages_athlete_first_message"]
        columns = {c.key for c in idx.columns}
        assert columns == {"athlete_id"}


class TestCoachingMessagePostWorkoutPartialUniqueIndex:
    """``post_workout`` has at most one message per ``activity_id`` —
    DB-enforced via partial unique index
    ``uq_coaching_messages_activity_post_workout`` on ``(activity_id)
    WHERE message_type = 'post_workout' AND activity_id IS NOT NULL``."""

    def test_post_workout_partial_unique_index_present(self) -> None:
        indexes = get_indexes(CoachingMessage)
        assert "uq_coaching_messages_activity_post_workout" in indexes, (
            "CoachingMessage must declare "
            "`uq_coaching_messages_activity_post_workout` to "
            "enforce one post_workout per activity."
        )

    def test_post_workout_index_is_unique(self) -> None:
        idx = get_indexes(CoachingMessage)["uq_coaching_messages_activity_post_workout"]
        assert idx.unique is True

    def test_post_workout_partial_predicate_present(self) -> None:
        idx = get_indexes(CoachingMessage)["uq_coaching_messages_activity_post_workout"]
        predicate = idx.dialect_options.get("postgresql", {}).get("where")
        assert predicate is not None, (
            "uq_coaching_messages_activity_post_workout must declare "
            "a postgresql_where predicate."
        )

    def test_post_workout_partial_predicate_includes_activity_id_not_null(
        self,
    ) -> None:
        """The partial predicate must include ``activity_id IS NOT
        NULL`` so non-post_workout rows with NULL activity_id are
        exempt from the uniqueness constraint."""
        idx = get_indexes(CoachingMessage)["uq_coaching_messages_activity_post_workout"]
        predicate = idx.dialect_options.get("postgresql", {}).get("where")
        rendered = str(predicate).lower()
        assert "message_type" in rendered, (
            "Predicate must include `message_type` filter."
        )
        assert "post_workout" in rendered, (
            "Predicate must constrain to `post_workout` type."
        )
        assert "activity_id" in rendered, (
            "Predicate must include `activity_id IS NOT NULL`."
        )
        assert "is not null" in rendered, (
            f"Predicate must short-circuit on NULL activity_id. "
            f"Got: {predicate!r}"
        )

    def test_post_workout_index_columns(self) -> None:
        idx = get_indexes(CoachingMessage)["uq_coaching_messages_activity_post_workout"]
        columns = {c.key for c in idx.columns}
        assert columns == {"activity_id"}


class TestCoachingMessageSecondaryIndexes:
    """``ix_coaching_messages_athlete_generated_at`` and
    ``ix_coaching_messages_athlete_type_generated_at`` support the
    GET /coach/messages feed and the per-type frequency guards."""

    def test_athlete_generated_at_index_present(self) -> None:
        indexes = get_indexes(CoachingMessage)
        assert "ix_coaching_messages_athlete_generated_at" in indexes
        idx = indexes["ix_coaching_messages_athlete_generated_at"]
        columns = {c.key for c in idx.columns}
        assert columns == {"athlete_id", "generated_at"}

    def test_athlete_type_generated_at_index_present(self) -> None:
        indexes = get_indexes(CoachingMessage)
        assert "ix_coaching_messages_athlete_type_generated_at" in indexes
        idx = indexes["ix_coaching_messages_athlete_type_generated_at"]
        columns = {c.key for c in idx.columns}
        assert columns == {
            "athlete_id",
            "message_type",
            "generated_at",
        }

    def test_twin_state_reverse_lookup_index_present(self) -> None:
        indexes = get_indexes(CoachingMessage)
        assert "ix_coaching_messages_twin_state" in indexes


# ---------------------------------------------------------------------------
# CHECK constraint — non-empty content.
# ---------------------------------------------------------------------------


class TestCoachingMessageContentCheck:
    """``content`` must be non-empty — empty strings would create
    blank-message rows that should be blocked at the DB layer."""

    def test_content_non_empty_check_present(self) -> None:
        checks = get_check_constraints(CoachingMessage)
        found = any(
            "length(content)" in get_check_text(c)
            and "> 0" in get_check_text(c)
            for c in checks
        )
        assert found, (
            "CoachingMessage must declare a CHECK constraint "
            "rejecting empty content (length(content) > 0)."
        )


# ---------------------------------------------------------------------------
# Append-only contract — no update()/delete() helpers on the mapper.
# ---------------------------------------------------------------------------


class TestCoachingMessageAppendOnlyContract:
    """CoachingMessage is immutable after creation. The model exposes
    no ``update()`` or ``delete()`` methods — the future repository
    (Phase 1.5) restricts to ``insert()`` only."""

    def test_no_update_helper_methods(self) -> None:
        for attr_name in dir(CoachingMessage):
            if attr_name.startswith("__"):
                continue
            attr = getattr(CoachingMessage, attr_name, None)
            if callable(attr) and attr_name in (
                "update",
                "delete",
                "save",
                "merge",
                "upsert",
                "replace",
                "put",
                "patch",
            ):
                assert False, (
                    f"CoachingMessage must not expose a `{attr_name}` "
                    "method — the table is append-only / insert-only."
                )

    def test_no_updated_at_column(self) -> None:
        """Append-only contract: ``updated_at`` would imply a
        mutation semantic that the schema must not permit."""
        assert "updated_at" not in get_columns(CoachingMessage), (
            "CoachingMessage must not carry an `updated_at` column — "
            "the row is immutable after creation."
        )


# ---------------------------------------------------------------------------
# Schema anti-goals — fields that must NOT appear on CoachingMessage.
# ---------------------------------------------------------------------------


class TestCoachingMessageSchemaAntiGoals:
    """Defence-in-depth tripwires: columns that would silently break
    the schema-only contract or violate the architecture."""

    @pytest.mark.parametrize(
        "forbidden_field",
        [
            # Soft-delete / mutation columns.
            "deleted_at",
            "is_deleted",
            "updated_at",
            # LLM internals belong on GenerationEvent, not here.
            "agent_name",
            "latency_ms",
            "input_token_count",
            "output_token_count",
            "failure_reason",
            "success",
            # Coaching draft / state machine.
            "draft",
            "is_published",
            "published_at",
        ],
    )
    def test_forbidden_columns_are_absent(self, forbidden_field: str) -> None:
        assert forbidden_field not in get_columns(CoachingMessage), (
            f"CoachingMessage must not carry `{forbidden_field}`. "
            "The row is immutable; LLM audit fields live on "
            "GenerationEvent."
        )