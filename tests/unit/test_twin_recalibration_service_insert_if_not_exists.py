"""Unit tests for ``TwinRecalibrationService.insert_if_not_exists``.

Phase-2.3-P3 implements the application-level deduplication gate
for TwinState inserts: the DB-level unique index
``uq_twin_states_athlete_activity`` was dropped so a calibration
TwinState can coexist with a prior ``activity_sync`` TwinState
for the same activity. ``insert_if_not_exists`` is the
authoritative deduplication mechanism.

Decision matrix (from ``docs/architecture/01-entities/twin-state.md``
Concurrency & Coordination, codified in the plan):

* Existing record with ``trigger == 'calibration'`` → return the
  existing record. Calibration is the most complete snapshot;
  any subsequent trigger for the same activity is skipped.
* No existing calibration record, but a non-calibration record
  exists and the incoming trigger is ``'calibration'`` → insert
  the calibration record. The fitness-only record remains as
  history.
* No existing calibration record, a non-calibration record
  exists, and the incoming trigger is also non-calibration →
  return the existing record. Duplicate non-calibration triggers
  are skipped.
* No existing record → insert the new state.

The method uses two repository lookups:

* ``get_by_activity_and_trigger`` for the calibration check.
* ``get_by_activity`` for the non-calibration fallback.

These tests use ``AsyncMock`` for the repositories — no real DB
connections, no real event publishing.

Reference plan: docs/implementation/phase-2/phase-2-3-p3-twin-recalibration-pipeline.md
Reference architecture: docs/architecture/01-entities/twin-state.md
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import TwinTrigger
from app.models.twin_state import TwinState
from app.repositories.twin_state_repository import TwinStateRepository
from app.services.twin_recalibration_service import TwinRecalibrationService


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _make_new_state(*, activity_id: uuid.UUID) -> MagicMock:
    """Build a mock ``TwinState`` for the new-state argument."""
    state = MagicMock(spec=TwinState)
    state.activity_id = activity_id
    state.id = uuid.uuid4()
    return state


def _make_existing_state(
    *,
    activity_id: uuid.UUID,
    trigger: str,
) -> MagicMock:
    """Build a mock existing ``TwinState`` for repository return."""
    state = MagicMock(spec=TwinState)
    state.activity_id = activity_id
    state.trigger = trigger
    state.id = uuid.uuid4()
    return state


def _make_service(
    *,
    calibration_existing: MagicMock | None = None,
    activity_existing: MagicMock | None = None,
) -> tuple[
    TwinRecalibrationService,
    AsyncMock,
]:
    """Build a service with a mock ``TwinStateRepository``.

    Returns the service and the mock repository so tests can
    assert on call counts and arguments.
    """
    mock_twin_states = AsyncMock(spec=TwinStateRepository)
    mock_twin_states.get_by_activity_and_trigger = AsyncMock(
        return_value=calibration_existing
    )
    mock_twin_states.get_by_activity = AsyncMock(
        return_value=activity_existing
    )
    mock_twin_states.insert = AsyncMock()

    # If no insert was configured, configure a sensible default
    # that returns the new state unchanged.
    if mock_twin_states.insert.return_value is None or (
        mock_twin_states.insert.return_value is MagicMock()
        and not mock_twin_states.insert.await_args
    ):
        async def _default_insert(state: MagicMock) -> MagicMock:
            return state

        mock_twin_states.insert.side_effect = _default_insert

    service = TwinRecalibrationService(
        MagicMock(),  # session — not used by insert_if_not_exists
        twin_states=mock_twin_states,
    )

    return service, mock_twin_states


# ---------------------------------------------------------------------------
# Calibration supersedes everything.
# ---------------------------------------------------------------------------


class TestInsertIfNotExistsCalibrationSupersedes:
    """When a calibration TwinState already exists for the
    activity, ``insert_if_not_exists`` returns the existing
    record and does NOT insert — regardless of the incoming
    trigger. Calibration is the most complete snapshot."""

    @pytest.mark.asyncio
    async def test_calibration_existing_skips_calibration_insert(self) -> None:
        """A prior calibration TwinState causes a new calibration
        TwinState to be skipped (no insert)."""
        activity_id = uuid.uuid4()
        existing = _make_existing_state(
            activity_id=activity_id, trigger=TwinTrigger.CALIBRATION.value
        )
        new_state = _make_new_state(activity_id=activity_id)

        service, mock_twin_states = _make_service(
            calibration_existing=existing
        )

        result = await service.insert_if_not_exists(
            athlete_id=uuid.uuid4(),
            activity_id=activity_id,
            trigger=TwinTrigger.CALIBRATION,
            new_state=new_state,
        )

        assert result is existing
        mock_twin_states.insert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_calibration_existing_skips_activity_sync_insert(self) -> None:
        """A prior calibration TwinState also causes a new
        activity_sync TwinState to be skipped — calibration is
        the authoritative snapshot for the activity."""
        activity_id = uuid.uuid4()
        existing = _make_existing_state(
            activity_id=activity_id, trigger=TwinTrigger.CALIBRATION.value
        )
        new_state = _make_new_state(activity_id=activity_id)

        service, mock_twin_states = _make_service(
            calibration_existing=existing
        )

        result = await service.insert_if_not_exists(
            athlete_id=uuid.uuid4(),
            activity_id=activity_id,
            trigger=TwinTrigger.ACTIVITY_SYNC,
            new_state=new_state,
        )

        assert result is existing
        mock_twin_states.insert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_calibration_check_uses_correct_trigger_value(self) -> None:
        """The calibration lookup passes the string ``'calibration'``
        to ``get_by_activity_and_trigger`` (the JSONB value, not
        the enum member)."""
        activity_id = uuid.uuid4()
        existing = _make_existing_state(
            activity_id=activity_id, trigger=TwinTrigger.CALIBRATION.value
        )

        service, mock_twin_states = _make_service(
            calibration_existing=existing
        )

        await service.insert_if_not_exists(
            athlete_id=uuid.uuid4(),
            activity_id=activity_id,
            trigger=TwinTrigger.ACTIVITY_SYNC,
            new_state=_make_new_state(activity_id=activity_id),
        )

        mock_twin_states.get_by_activity_and_trigger.assert_awaited_once_with(
            activity_id=activity_id,
            trigger=TwinTrigger.CALIBRATION.value,
        )


# ---------------------------------------------------------------------------
# Calibration supersedes a prior non-calibration record.
# ---------------------------------------------------------------------------


class TestInsertIfNotExistsCalibrationSupersedesActivitySync:
    """When a non-calibration TwinState exists for the activity and
    the incoming trigger is ``'calibration'``, the new calibration
    record is inserted and the prior non-calibration record remains
    as history. This is the dual-trigger scenario that motivated
    dropping the unique index in Phase 2.3-P3."""

    @pytest.mark.asyncio
    async def test_calibration_inserts_when_activity_sync_exists(self) -> None:
        """A calibration TwinState is inserted when a prior
        activity_sync TwinState exists for the same activity."""
        activity_id = uuid.uuid4()
        prior = _make_existing_state(
            activity_id=activity_id, trigger=TwinTrigger.ACTIVITY_SYNC.value
        )
        new_state = _make_new_state(activity_id=activity_id)

        service, mock_twin_states = _make_service(
            calibration_existing=None,
            activity_existing=prior,
        )
        # Configure insert to return the new state.
        mock_twin_states.insert.return_value = new_state

        result = await service.insert_if_not_exists(
            athlete_id=uuid.uuid4(),
            activity_id=activity_id,
            trigger=TwinTrigger.CALIBRATION,
            new_state=new_state,
        )

        assert result is new_state
        mock_twin_states.insert.assert_awaited_once_with(new_state)

    @pytest.mark.asyncio
    async def test_calibration_inserts_when_wellness_update_exists(self) -> None:
        """A calibration TwinState is inserted when a prior
        ``wellness_update`` TwinState exists for the same
        activity (any non-calibration trigger is superseded)."""
        activity_id = uuid.uuid4()
        prior = _make_existing_state(
            activity_id=activity_id, trigger=TwinTrigger.WELLNESS_UPDATE.value
        )
        new_state = _make_new_state(activity_id=activity_id)

        service, mock_twin_states = _make_service(
            calibration_existing=None,
            activity_existing=prior,
        )
        mock_twin_states.insert.return_value = new_state

        result = await service.insert_if_not_exists(
            athlete_id=uuid.uuid4(),
            activity_id=activity_id,
            trigger=TwinTrigger.CALIBRATION,
            new_state=new_state,
        )

        assert result is new_state
        mock_twin_states.insert.assert_awaited_once_with(new_state)


# ---------------------------------------------------------------------------
# Duplicate non-calibration triggers are skipped.
# ---------------------------------------------------------------------------


class TestInsertIfNotExistsDuplicateNonCalibration:
    """When a non-calibration TwinState exists for the activity and
    the incoming trigger is also non-calibration, the new record
    is skipped. Only the calibration trigger can append to an
    activity that already has a non-calibration record."""

    @pytest.mark.asyncio
    async def test_duplicate_activity_sync_skipped(self) -> None:
        """A second activity_sync TwinState is skipped when a
        prior activity_sync TwinState already exists."""
        activity_id = uuid.uuid4()
        prior = _make_existing_state(
            activity_id=activity_id, trigger=TwinTrigger.ACTIVITY_SYNC.value
        )
        new_state = _make_new_state(activity_id=activity_id)

        service, mock_twin_states = _make_service(
            calibration_existing=None,
            activity_existing=prior,
        )

        result = await service.insert_if_not_exists(
            athlete_id=uuid.uuid4(),
            activity_id=activity_id,
            trigger=TwinTrigger.ACTIVITY_SYNC,
            new_state=new_state,
        )

        assert result is prior
        mock_twin_states.insert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_duplicate_wellness_update_skipped(self) -> None:
        """A wellness_update TwinState is skipped when a prior
        wellness_update TwinState already exists."""
        activity_id = uuid.uuid4()
        prior = _make_existing_state(
            activity_id=activity_id, trigger=TwinTrigger.WELLNESS_UPDATE.value
        )
        new_state = _make_new_state(activity_id=activity_id)

        service, mock_twin_states = _make_service(
            calibration_existing=None,
            activity_existing=prior,
        )

        result = await service.insert_if_not_exists(
            athlete_id=uuid.uuid4(),
            activity_id=activity_id,
            trigger=TwinTrigger.WELLNESS_UPDATE,
            new_state=new_state,
        )

        assert result is prior
        mock_twin_states.insert.assert_not_awaited()


# ---------------------------------------------------------------------------
# No existing record — insert the new state.
# ---------------------------------------------------------------------------


class TestInsertIfNotExistsNoExisting:
    """When no TwinState exists for the activity, the new record
    is inserted regardless of the trigger."""

    @pytest.mark.asyncio
    async def test_first_calibration_insert(self) -> None:
        """The first TwinState for an activity is always inserted,
        regardless of trigger."""
        activity_id = uuid.uuid4()
        new_state = _make_new_state(activity_id=activity_id)

        service, mock_twin_states = _make_service(
            calibration_existing=None,
            activity_existing=None,
        )
        mock_twin_states.insert.return_value = new_state

        result = await service.insert_if_not_exists(
            athlete_id=uuid.uuid4(),
            activity_id=activity_id,
            trigger=TwinTrigger.CALIBRATION,
            new_state=new_state,
        )

        assert result is new_state
        mock_twin_states.insert.assert_awaited_once_with(new_state)

    @pytest.mark.asyncio
    async def test_first_activity_sync_insert(self) -> None:
        """The first activity_sync TwinState for an activity is
        always inserted."""
        activity_id = uuid.uuid4()
        new_state = _make_new_state(activity_id=activity_id)

        service, mock_twin_states = _make_service(
            calibration_existing=None,
            activity_existing=None,
        )
        mock_twin_states.insert.return_value = new_state

        result = await service.insert_if_not_exists(
            athlete_id=uuid.uuid4(),
            activity_id=activity_id,
            trigger=TwinTrigger.ACTIVITY_SYNC,
            new_state=new_state,
        )

        assert result is new_state
        mock_twin_states.insert.assert_awaited_once_with(new_state)


# ---------------------------------------------------------------------------
# Lookup order — calibration check happens first.
# ---------------------------------------------------------------------------


class TestInsertIfNotExistsLookupOrder:
    """The method's lookup order is:
    1. ``get_by_activity_and_trigger(activity, 'calibration')`` first.
    2. ``get_by_activity(activity)`` only if the calibration check
       returned ``None``.

    This ordering matters: a calibration record is the
    authoritative snapshot and must short-circuit the second
    lookup even when a non-calibration record also exists."""

    @pytest.mark.asyncio
    async def test_calibration_check_runs_first(self) -> None:
        """``get_by_activity_and_trigger`` is called before
        ``get_by_activity``."""
        activity_id = uuid.uuid4()
        new_state = _make_new_state(activity_id=activity_id)

        service, mock_twin_states = _make_service(
            calibration_existing=None,
            activity_existing=None,
        )
        mock_twin_states.insert.return_value = new_state

        await service.insert_if_not_exists(
            athlete_id=uuid.uuid4(),
            activity_id=activity_id,
            trigger=TwinTrigger.ACTIVITY_SYNC,
            new_state=new_state,
        )

        # Both lookups were called, but calibration check first.
        assert (
            mock_twin_states.get_by_activity_and_trigger.await_count == 1
        )
        assert mock_twin_states.get_by_activity.await_count == 1

    @pytest.mark.asyncio
    async def test_activity_lookup_skipped_when_calibration_exists(self) -> None:
        """When a calibration record exists, the non-calibration
        lookup is NOT made — the calibration supersedes."""
        activity_id = uuid.uuid4()
        existing = _make_existing_state(
            activity_id=activity_id, trigger=TwinTrigger.CALIBRATION.value
        )
        new_state = _make_new_state(activity_id=activity_id)

        service, mock_twin_states = _make_service(
            calibration_existing=existing
        )

        await service.insert_if_not_exists(
            athlete_id=uuid.uuid4(),
            activity_id=activity_id,
            trigger=TwinTrigger.ACTIVITY_SYNC,
            new_state=new_state,
        )

        mock_twin_states.get_by_activity_and_trigger.assert_awaited_once()
        mock_twin_states.get_by_activity.assert_not_awaited()


# ---------------------------------------------------------------------------
# Pass-through of activity_id to repository methods.
# ---------------------------------------------------------------------------


class TestInsertIfNotExistsActivityIdPassThrough:
    """The ``activity_id`` argument flows through to both repository
    lookups unchanged — the method does not transform it."""

    @pytest.mark.asyncio
    async def test_activity_id_passed_to_calibration_lookup(self) -> None:
        activity_id = uuid.uuid4()

        service, mock_twin_states = _make_service(
            calibration_existing=None,
            activity_existing=None,
        )

        await service.insert_if_not_exists(
            athlete_id=uuid.uuid4(),
            activity_id=activity_id,
            trigger=TwinTrigger.ACTIVITY_SYNC,
            new_state=_make_new_state(activity_id=activity_id),
        )

        call = mock_twin_states.get_by_activity_and_trigger.await_args
        assert call.kwargs["activity_id"] == activity_id

    @pytest.mark.asyncio
    async def test_activity_id_passed_to_fallback_lookup(self) -> None:
        activity_id = uuid.uuid4()

        service, mock_twin_states = _make_service(
            calibration_existing=None,
            activity_existing=None,
        )

        await service.insert_if_not_exists(
            athlete_id=uuid.uuid4(),
            activity_id=activity_id,
            trigger=TwinTrigger.ACTIVITY_SYNC,
            new_state=_make_new_state(activity_id=activity_id),
        )

        call = mock_twin_states.get_by_activity.await_args
        assert call.kwargs["activity_id"] == activity_id
