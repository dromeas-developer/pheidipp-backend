"""Integration tests for ``AthletePhysiologyRepository.update_in_place`` at the real-DB layer.

The unit tests in
``tests/unit/test_athlete_physiology_repository_update_in_place.py``
exercise ``update_in_place`` with ``AsyncMock``-backed sessions, so
they only prove the in-memory branching is correct. This integration
layer exercises the *real* test database to confirm:

* JSONB column mutations land in the database column verbatim — the
  new value is visible to a fresh SELECT after commit.
* The ``updated_at`` ``onupdate=`` SQLAlchemy hook fires on the
  mutation (the timestamp changes).
* The row's ``id`` is preserved across the update — no second row
  is created (the repository's contract: mutate, never insert).
* Passing ``None`` for ``cp`` / ``max_hr`` (nullable columns) clears
  the column to NULL — distinct from the ``UNSET_SENTINEL`` (which
  means "do not touch").
* Passing the ``UNSET_SENTINEL`` for ``cp`` / ``max_hr`` leaves the
  column unchanged.
* Passing ``None`` for ``lt1`` / ``lt2`` (non-nullable columns)
  leaves the column unchanged — ``None`` is the "do not touch"
  sentinel for these columns.
* ``RuntimeError`` is raised when no row exists for ``athlete_id`` —
  the service layer treats this as a data-integrity failure.

Reference plan: docs/implementation/phase-2/phase-2-3-p2-physiology-update.md
Reference architecture: docs/architecture/01-entities/athlete-physiology.md
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Dict, Optional

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete_physiology import AthletePhysiology
from app.repositories.athlete_physiology_repository import (
    UNSET_SENTINEL,
    AthletePhysiologyRepository,
)
from tests.utils.factories import make_athlete


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _state(
    *,
    value: float = 165.0,
    uncertainty: float = 1.0,
    prior_weight: float = 0.5,
    dominant_source: str = "training_hr_deflection",
    last_observation_date: str = "2026-05-01",
) -> Dict[str, Any]:
    """Build a full ``PhysiologyParameterState`` dict."""
    return {
        "value": value,
        "uncertainty": uncertainty,
        "prior_weight": prior_weight,
        "dominant_source": dominant_source,
        "last_observation_date": last_observation_date,
    }


async def _create_physiology_row(
    db_session: AsyncSession,
    *,
    athlete_id: uuid.UUID,
    lt1: Optional[Dict[str, Any]] = None,
    lt2: Optional[Dict[str, Any]] = None,
    cp: Optional[Dict[str, Any]] = None,
    max_hr: Optional[Dict[str, Any]] = None,
) -> AthletePhysiology:
    """Insert a real ``AthletePhysiology`` row with the given JSONB
    columns."""
    row = AthletePhysiology(
        athlete_id=athlete_id,
        lt1=lt1 if lt1 is not None else {"hr": None, "power": None, "pace": None},
        lt2=lt2 if lt2 is not None else {"hr": None, "power": None, "pace": None},
        cp=cp,
        max_hr=max_hr,
    )
    db_session.add(row)
    await db_session.flush()
    return row


# ---------------------------------------------------------------------------
# lt1 — update in place.
# ---------------------------------------------------------------------------


class TestUpdateInPlaceLt1Persistence:
    """``update_in_place(lt1=...)`` mutates the ``lt1`` JSONB
    column at the real-DB layer."""

    @pytest.mark.asyncio
    async def test_lt1_mapping_persists_in_db(
        self, db_session: AsyncSession
    ) -> None:
        """A mapping passed as ``lt1`` is persisted to the ``lt1``
        column — a fresh SELECT after commit returns the new
        value verbatim."""
        athlete = await make_athlete(db_session)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            lt1={
                "hr": _state(value=150.0),
                "power": None,
                "pace": None,
            },
        )
        new_lt1 = {
            "hr": _state(value=152.0, prior_weight=2.0),
            "power": None,
            "pace": None,
        }

        repo = AthletePhysiologyRepository(db_session)
        result = await repo.update_in_place(athlete.id, lt1=new_lt1)
        await db_session.commit()

        # The returned in-memory row reflects the new value.
        assert result.lt1 == new_lt1

        # A fresh SELECT confirms the mutation persisted.
        fresh = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()[0]
        assert fresh.lt1 == new_lt1
        assert fresh.lt1["hr"]["value"] == pytest.approx(152.0)
        assert fresh.lt1["hr"]["prior_weight"] == pytest.approx(2.0)

    @pytest.mark.asyncio
    async def test_lt1_unchanged_when_not_passed(
        self, db_session: AsyncSession
    ) -> None:
        """``lt1`` is unchanged when not passed (default
        ``None``). The repository's "do not touch" semantics for
        the non-nullable column are preserved at the DB layer."""
        original_lt1 = {
            "hr": _state(value=150.0),
            "power": None,
            "pace": None,
        }
        athlete = await make_athlete(db_session)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            lt1=original_lt1,
        )

        repo = AthletePhysiologyRepository(db_session)
        await repo.update_in_place(athlete.id)
        await db_session.commit()

        fresh = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()[0]
        assert fresh.lt1 == original_lt1


# ---------------------------------------------------------------------------
# lt2 — update in place.
# ---------------------------------------------------------------------------


class TestUpdateInPlaceLt2Persistence:
    """``update_in_place(lt2=...)`` mutates the ``lt2`` JSONB
    column at the real-DB layer."""

    @pytest.mark.asyncio
    async def test_lt2_mapping_persists_in_db(
        self, db_session: AsyncSession
    ) -> None:
        """A mapping passed as ``lt2`` is persisted to the
        ``lt2`` column."""
        athlete = await make_athlete(db_session)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            lt2={
                "hr": _state(value=170.0),
                "power": None,
                "pace": None,
            },
        )
        new_lt2 = {
            "hr": _state(value=172.0, prior_weight=3.0),
            "power": None,
            "pace": None,
        }

        repo = AthletePhysiologyRepository(db_session)
        await repo.update_in_place(athlete.id, lt2=new_lt2)
        await db_session.commit()

        fresh = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()[0]
        assert fresh.lt2 == new_lt2
        assert fresh.lt2["hr"]["value"] == pytest.approx(172.0)
        assert fresh.lt2["hr"]["prior_weight"] == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# cp — null/non-null/sentinel transitions.
# ---------------------------------------------------------------------------


class TestUpdateInPlaceCpPersistence:
    """``update_in_place(cp=...)`` mutates the nullable ``cp``
    JSONB column at the real-DB layer."""

    @pytest.mark.asyncio
    async def test_cp_null_to_non_null_persists(
        self, db_session: AsyncSession
    ) -> None:
        """``cp`` transitions from NULL to a non-null
        ``PhysiologyParameterState`` at the real-DB layer."""
        athlete = await make_athlete(db_session)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            cp=None,
        )

        repo = AthletePhysiologyRepository(db_session)
        new_cp = _state(value=260.0, prior_weight=2.0)
        await repo.update_in_place(athlete.id, cp=new_cp)
        await db_session.commit()

        fresh = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()[0]
        assert fresh.cp is not None
        assert fresh.cp == new_cp
        assert fresh.cp["value"] == pytest.approx(260.0)

    @pytest.mark.asyncio
    async def test_cp_non_null_to_null_clears(
        self, db_session: AsyncSession
    ) -> None:
        """``cp`` transitions from non-null to NULL when ``None``
        is passed explicitly (nullable column contract)."""
        athlete = await make_athlete(db_session)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            cp=_state(value=260.0),
        )

        repo = AthletePhysiologyRepository(db_session)
        await repo.update_in_place(athlete.id, cp=None)
        await db_session.commit()

        fresh = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()[0]
        assert fresh.cp is None

    @pytest.mark.asyncio
    async def test_cp_unchanged_when_unset_sentinel(
        self, db_session: AsyncSession
    ) -> None:
        """``cp`` is unchanged when ``UNSET_SENTINEL`` is passed —
        the sentinel means "do not touch", distinct from
        ``None`` (which clears the column)."""
        original_cp = _state(value=260.0)
        athlete = await make_athlete(db_session)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            cp=original_cp,
        )

        repo = AthletePhysiologyRepository(db_session)
        await repo.update_in_place(athlete.id, cp=UNSET_SENTINEL)
        await db_session.commit()

        fresh = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()[0]
        assert fresh.cp == original_cp

    @pytest.mark.asyncio
    async def test_cp_unchanged_when_not_passed(
        self, db_session: AsyncSession
    ) -> None:
        """``cp`` is unchanged when not passed — the default
        ``UNSET_SENTINEL`` sentinel is applied automatically."""
        original_cp = _state(value=260.0)
        athlete = await make_athlete(db_session)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            cp=original_cp,
        )

        repo = AthletePhysiologyRepository(db_session)
        await repo.update_in_place(athlete.id)
        await db_session.commit()

        fresh = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()[0]
        assert fresh.cp == original_cp


# ---------------------------------------------------------------------------
# max_hr — null/non-null/sentinel transitions.
# ---------------------------------------------------------------------------


class TestUpdateInPlaceMaxHrPersistence:
    """``update_in_place(max_hr=...)`` mutates the nullable
    ``max_hr`` JSONB column at the real-DB layer."""

    @pytest.mark.asyncio
    async def test_max_hr_null_to_non_null_persists(
        self, db_session: AsyncSession
    ) -> None:
        """``max_hr`` transitions from NULL to a non-null state."""
        athlete = await make_athlete(db_session)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            max_hr=None,
        )

        repo = AthletePhysiologyRepository(db_session)
        new_max_hr = _state(value=195.0, prior_weight=1.0)
        await repo.update_in_place(athlete.id, max_hr=new_max_hr)
        await db_session.commit()

        fresh = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()[0]
        assert fresh.max_hr is not None
        assert fresh.max_hr == new_max_hr

    @pytest.mark.asyncio
    async def test_max_hr_non_null_to_null_clears(
        self, db_session: AsyncSession
    ) -> None:
        """``max_hr`` transitions from non-null to NULL when
        ``None`` is passed explicitly."""
        athlete = await make_athlete(db_session)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            max_hr=_state(value=195.0),
        )

        repo = AthletePhysiologyRepository(db_session)
        await repo.update_in_place(athlete.id, max_hr=None)
        await db_session.commit()

        fresh = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()[0]
        assert fresh.max_hr is None

    @pytest.mark.asyncio
    async def test_max_hr_unchanged_when_unset_sentinel(
        self, db_session: AsyncSession
    ) -> None:
        """``max_hr`` is unchanged when ``UNSET_SENTINEL`` is
        passed."""
        original_max_hr = _state(value=195.0)
        athlete = await make_athlete(db_session)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            max_hr=original_max_hr,
        )

        repo = AthletePhysiologyRepository(db_session)
        await repo.update_in_place(athlete.id, max_hr=UNSET_SENTINEL)
        await db_session.commit()

        fresh = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()[0]
        assert fresh.max_hr == original_max_hr


# ---------------------------------------------------------------------------
# updated_at hook fires.
# ---------------------------------------------------------------------------


class TestUpdateInPlaceUpdatedAtHook:
    """The ``AthletePhysiology.updated_at`` ``onupdate=`` SQLAlchemy
    hook fires on ``update_in_place``."""

    @pytest.mark.asyncio
    async def test_updated_at_changes_after_update(
        self, db_session: AsyncSession
    ) -> None:
        """``updated_at`` advances when ``update_in_place`` is
        called — verified by capturing the pre-call value, sleeping
        a small interval, calling ``update_in_place``, and
        asserting the post-call value is greater."""
        athlete = await make_athlete(db_session)
        row = await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            lt1={
                "hr": _state(value=150.0),
                "power": None,
                "pace": None,
            },
        )
        await db_session.commit()
        original_updated_at = row.updated_at

        # ``updated_at`` is a ``DateTime(timezone=True)`` —
        # second-precision is the minimum the DB will store.
        await asyncio.sleep(1.1)

        repo = AthletePhysiologyRepository(db_session)
        new_lt1 = {
            "hr": _state(value=152.0),
            "power": None,
            "pace": None,
        }
        await repo.update_in_place(athlete.id, lt1=new_lt1)
        await db_session.commit()

        # Refresh to read the latest updated_at from the DB.
        await db_session.refresh(row)
        assert row.updated_at > original_updated_at

    # NOTE: the previous
    # ``test_updated_at_changes_even_with_no_column_mutations``
    # test has been removed. The original test asserted that
    # ``updated_at`` advances on a ``flush()`` with no column
    # mutations, but SQLAlchemy's ``onupdate=`` hook only fires
    # when an actual ``UPDATE`` statement is issued — i.e. when
    # at least one column is mutated. Calling ``update_in_place``
    # with no parameters is a no-op at the DB layer and the
    # ``onupdate=`` hook does NOT fire. The test was asserting
    # the wrong behaviour; the correct semantics are pinned by
    # ``test_updated_at_changes_after_update`` above (a
    # mutated-column call DOES fire the hook).


# ---------------------------------------------------------------------------
# No row exists — RuntimeError.
# ---------------------------------------------------------------------------


class TestUpdateInPlaceNoRow:
    """``update_in_place`` raises ``RuntimeError`` when no row
    exists for ``athlete_id``."""

    @pytest.mark.asyncio
    async def test_raises_runtime_error_when_no_row(
        self, db_session: AsyncSession
    ) -> None:
        """A missing row raises ``RuntimeError`` with the expected
        message — the service layer treats this as a
        data-integrity failure."""
        athlete = await make_athlete(db_session)
        # No AthletePhysiology row is created for this athlete.
        repo = AthletePhysiologyRepository(db_session)

        with pytest.raises(RuntimeError) as exc_info:
            await repo.update_in_place(
                athlete.id,
                lt1={
                    "hr": _state(value=150.0),
                    "power": None,
                    "pace": None,
                },
            )

        assert (
            str(exc_info.value)
            == f"no AthletePhysiology row for athlete {athlete.id}"
        )

    @pytest.mark.asyncio
    async def test_no_flush_when_no_row(
        self, db_session: AsyncSession
    ) -> None:
        """No rows are inserted when the lookup fails — the
        repository does not fall back to ``add``."""
        athlete = await make_athlete(db_session)
        repo = AthletePhysiologyRepository(db_session)

        with pytest.raises(RuntimeError):
            await repo.update_in_place(
                athlete.id,
                lt1={
                    "hr": _state(value=150.0),
                    "power": None,
                    "pace": None,
                },
            )

        # No row was created as a side effect of the failed call.
        rows = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert len(rows) == 0


# ---------------------------------------------------------------------------
# Row id preserved across updates.
# ---------------------------------------------------------------------------


class TestUpdateInPlaceRowIdPreserved:
    """The ``AthletePhysiology.id`` is preserved across the
    update — no second row is created."""

    @pytest.mark.asyncio
    async def test_row_id_unchanged_after_update(
        self, db_session: AsyncSession
    ) -> None:
        """After ``update_in_place``, the row's ``id`` is the
        same as before — the repository mutates the existing
        row, never creates a new one."""
        athlete = await make_athlete(db_session)
        row = await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            lt1={
                "hr": _state(value=150.0),
                "power": None,
                "pace": None,
            },
            lt2={
                "hr": _state(value=170.0),
                "power": None,
                "pace": None,
            },
            cp=_state(value=260.0),
        )
        original_id = row.id

        repo = AthletePhysiologyRepository(db_session)
        await repo.update_in_place(
            athlete.id,
            lt1={
                "hr": _state(value=152.0),
                "power": None,
                "pace": None,
            },
            lt2={
                "hr": _state(value=172.0),
                "power": None,
                "pace": None,
            },
            cp=_state(value=265.0),
        )
        await db_session.commit()

        # Exactly one row for the athlete.
        rows = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        # The row's id is preserved.
        assert rows[0].id == original_id
