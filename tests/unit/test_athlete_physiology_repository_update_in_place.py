"""Unit tests for ``AthletePhysiologyRepository.update_in_place``.

Phase-2.3-P2 extends ``AthletePhysiologyRepository`` with an
``update_in_place`` method that mutates the existing row in place
without creating a new one. The method flushes but does NOT commit —
the caller (worker task in Phase-2.3-P3) owns the commit boundary.

The method uses an explicit ``UNSET_SENTINEL`` to distinguish
"caller did not pass the argument" (no-op) from "caller passed
``None``" (clear the nullable column) for ``cp`` / ``max_hr``.
For ``lt1`` / ``lt2`` (non-nullable columns), ``None`` means
"do not touch".

Reference plan: docs/implementation/phase-2/phase-2-3-p2-physiology-update.md
Reference architecture: docs/architecture/01-entities/athlete-physiology.md
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete_physiology import AthletePhysiology
from app.repositories.athlete_physiology_repository import (
    UNSET_SENTINEL,
    AthletePhysiologyRepository,
)


# ---------------------------------------------------------------------------
# Helpers — build the JSONB dict shapes and ORM model instances.
# ---------------------------------------------------------------------------


def _state(
    *,
    value: float = 165.0,
    uncertainty: float = 1.0,
    prior_weight: float = 0.5,
    dominant_source: str = "training_hr_deflection",
    last_observation_date: str = "2026-05-01",
) -> Dict[str, Any]:
    """Build a ``PhysiologyParameterState`` dict."""
    return {
        "value": value,
        "uncertainty": uncertainty,
        "prior_weight": prior_weight,
        "dominant_source": dominant_source,
        "last_observation_date": last_observation_date,
    }


def _physiology_row(
    *,
    lt1: Optional[Dict[str, Any]] = None,
    lt2: Optional[Dict[str, Any]] = None,
    cp: Optional[Dict[str, Any]] = None,
    max_hr: Optional[Dict[str, Any]] = None,
) -> AthletePhysiology:
    """Build an in-memory ``AthletePhysiology`` row with the given
    JSONB columns. ``lt1`` and ``lt2`` default to the empty
    three-dimension container so the row is constructible without
    raising on the non-nullable columns."""
    return AthletePhysiology(
        athlete_id=uuid.uuid4(),
        lt1=lt1 if lt1 is not None else {"hr": None, "power": None, "pace": None},
        lt2=lt2 if lt2 is not None else {"hr": None, "power": None, "pace": None},
        cp=cp,
        max_hr=max_hr,
    )


def _make_repo_with_row(
    row: AthletePhysiology,
) -> tuple[AthletePhysiologyRepository, AsyncMock]:
    """Build a repository whose ``get_by_athlete_id`` returns ``row``.

    Returns the repo and the mock session so tests can assert against
    ``session.flush``, ``session.commit``, etc.
    """
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = row
    mock_session.execute.return_value = mock_result

    repo = AthletePhysiologyRepository(mock_session)
    return repo, mock_session


def _make_repo_without_row() -> tuple[AthletePhysiologyRepository, AsyncMock]:
    """Build a repository whose ``get_by_athlete_id`` returns ``None``."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    repo = AthletePhysiologyRepository(mock_session)
    return repo, mock_session


# ---------------------------------------------------------------------------
# update_in_place — happy path: each parameter updated independently.
# ---------------------------------------------------------------------------


class TestUpdateInPlaceLt1:
    """``update_in_place`` updates ``lt1`` when a mapping is passed."""

    @pytest.mark.asyncio
    async def test_lt1_updated_when_mapping_passed(self) -> None:
        """A mapping passed as ``lt1`` is assigned to ``row.lt1``."""
        row = _physiology_row(
            lt1={"hr": _state(value=150.0), "power": None, "pace": None},
        )
        repo, mock_session = _make_repo_with_row(row)
        new_lt1 = {"hr": _state(value=152.0), "power": None, "pace": None}

        result = await repo.update_in_place(
            row.athlete_id, lt1=new_lt1
        )

        assert result.lt1 == new_lt1
        mock_session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lt1_unchanged_when_not_passed(self) -> None:
        """``lt1`` is unchanged when not passed (default ``None``)."""
        original_lt1 = {"hr": _state(value=150.0), "power": None, "pace": None}
        row = _physiology_row(lt1=original_lt1)
        repo, _ = _make_repo_with_row(row)

        result = await repo.update_in_place(row.athlete_id)

        assert result.lt1 == original_lt1

    @pytest.mark.asyncio
    async def test_lt1_unchanged_when_explicit_none(self) -> None:
        """``lt1`` is unchanged when ``None`` is passed explicitly
        (same as default — non-nullable column sentinel)."""
        original_lt1 = {"hr": _state(value=150.0), "power": None, "pace": None}
        row = _physiology_row(lt1=original_lt1)
        repo, _ = _make_repo_with_row(row)

        result = await repo.update_in_place(row.athlete_id, lt1=None)

        assert result.lt1 == original_lt1

    @pytest.mark.asyncio
    async def test_lt2_cp_max_hr_unchanged_when_only_lt1_updated(self) -> None:
        """Only ``lt1`` is touched when only ``lt1`` is passed."""
        original_lt2 = {"hr": _state(value=175.0), "power": None, "pace": None}
        original_cp = _state(value=260.0)
        original_max_hr = _state(value=195.0)
        row = _physiology_row(
            lt1={"hr": _state(value=150.0), "power": None, "pace": None},
            lt2=original_lt2,
            cp=original_cp,
            max_hr=original_max_hr,
        )
        repo, _ = _make_repo_with_row(row)
        new_lt1 = {"hr": _state(value=152.0), "power": None, "pace": None}

        result = await repo.update_in_place(row.athlete_id, lt1=new_lt1)

        assert result.lt1 == new_lt1
        assert result.lt2 == original_lt2
        assert result.cp == original_cp
        assert result.max_hr == original_max_hr


class TestUpdateInPlaceLt2:
    """``update_in_place`` updates ``lt2`` when a mapping is passed."""

    @pytest.mark.asyncio
    async def test_lt2_updated_when_mapping_passed(self) -> None:
        """A mapping passed as ``lt2`` is assigned to ``row.lt2``."""
        row = _physiology_row(
            lt2={"hr": _state(value=175.0), "power": None, "pace": None},
        )
        repo, mock_session = _make_repo_with_row(row)
        new_lt2 = {"hr": _state(value=177.0), "power": None, "pace": None}

        result = await repo.update_in_place(
            row.athlete_id, lt2=new_lt2
        )

        assert result.lt2 == new_lt2
        mock_session.flush.assert_awaited_once()


class TestUpdateInPlaceCp:
    """``update_in_place`` updates ``cp`` when a mapping is passed,
    clears it when ``None`` is passed, and leaves it untouched when
    the sentinel is passed."""

    @pytest.mark.asyncio
    async def test_cp_updated_when_mapping_passed(self) -> None:
        """A mapping passed as ``cp`` is assigned to ``row.cp``."""
        row = _physiology_row(cp=_state(value=260.0))
        repo, mock_session = _make_repo_with_row(row)
        new_cp = _state(value=265.0)

        result = await repo.update_in_place(row.athlete_id, cp=new_cp)

        assert result.cp == new_cp
        mock_session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cp_cleared_to_none_when_explicit_none(self) -> None:
        """``cp`` is cleared to ``None`` when ``None`` is passed
        explicitly (nullable column — ``None`` is a legitimate value)."""
        row = _physiology_row(cp=_state(value=260.0))
        repo, _ = _make_repo_with_row(row)

        result = await repo.update_in_place(row.athlete_id, cp=None)

        assert result.cp is None

    @pytest.mark.asyncio
    async def test_cp_unchanged_when_unset_sentinel_passed(self) -> None:
        """``cp`` is unchanged when ``UNSET_SENTINEL`` is passed
        explicitly (same as default — sentinel means "do not touch")."""
        original_cp = _state(value=260.0)
        row = _physiology_row(cp=original_cp)
        repo, _ = _make_repo_with_row(row)

        result = await repo.update_in_place(
            row.athlete_id, cp=UNSET_SENTINEL
        )

        assert result.cp == original_cp

    @pytest.mark.asyncio
    async def test_cp_unchanged_when_not_passed(self) -> None:
        """``cp`` is unchanged when not passed (default sentinel)."""
        original_cp = _state(value=260.0)
        row = _physiology_row(cp=original_cp)
        repo, _ = _make_repo_with_row(row)

        result = await repo.update_in_place(row.athlete_id)

        assert result.cp == original_cp


class TestUpdateInPlaceMaxHr:
    """``update_in_place`` updates ``max_hr`` when a mapping is passed,
    clears it when ``None`` is passed, and leaves it untouched when
    the sentinel is passed."""

    @pytest.mark.asyncio
    async def test_max_hr_updated_when_mapping_passed(self) -> None:
        """A mapping passed as ``max_hr`` is assigned to ``row.max_hr``."""
        row = _physiology_row(max_hr=_state(value=195.0))
        repo, mock_session = _make_repo_with_row(row)
        new_max_hr = _state(value=192.0)

        result = await repo.update_in_place(
            row.athlete_id, max_hr=new_max_hr
        )

        assert result.max_hr == new_max_hr
        mock_session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_max_hr_cleared_to_none_when_explicit_none(self) -> None:
        """``max_hr`` is cleared to ``None`` when ``None`` is passed
        explicitly."""
        row = _physiology_row(max_hr=_state(value=195.0))
        repo, _ = _make_repo_with_row(row)

        result = await repo.update_in_place(row.athlete_id, max_hr=None)

        assert result.max_hr is None

    @pytest.mark.asyncio
    async def test_max_hr_unchanged_when_unset_sentinel_passed(self) -> None:
        """``max_hr`` is unchanged when ``UNSET_SENTINEL`` is passed."""
        original_max_hr = _state(value=195.0)
        row = _physiology_row(max_hr=original_max_hr)
        repo, _ = _make_repo_with_row(row)

        result = await repo.update_in_place(
            row.athlete_id, max_hr=UNSET_SENTINEL
        )

        assert result.max_hr == original_max_hr


# ---------------------------------------------------------------------------
# update_in_place — multiple parameters at once.
# ---------------------------------------------------------------------------


class TestUpdateInPlaceMultipleParameters:
    """``update_in_place`` can update multiple parameters in a single
    call."""

    @pytest.mark.asyncio
    async def test_multiple_parameters_updated_together(self) -> None:
        """Multiple parameters passed in one call are all updated."""
        row = _physiology_row(
            lt1={"hr": _state(value=150.0), "power": None, "pace": None},
            lt2={"hr": _state(value=175.0), "power": None, "pace": None},
            cp=_state(value=260.0),
            max_hr=_state(value=195.0),
        )
        repo, mock_session = _make_repo_with_row(row)
        new_lt1 = {"hr": _state(value=148.0), "power": None, "pace": None}
        new_cp = None  # clear cp
        new_max_hr = _state(value=190.0)

        result = await repo.update_in_place(
            row.athlete_id,
            lt1=new_lt1,
            cp=new_cp,
            max_hr=new_max_hr,
        )

        assert result.lt1 == new_lt1
        assert result.cp is None
        assert result.max_hr == new_max_hr
        # lt2 was not passed → unchanged.
        assert result.lt2 == {"hr": _state(value=175.0), "power": None, "pace": None}
        mock_session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# update_in_place — flush and commit semantics.
# ---------------------------------------------------------------------------


class TestUpdateInPlaceFlushAndCommit:
    """``update_in_place`` flushes the session but does NOT commit."""

    @pytest.mark.asyncio
    async def test_flushes_session(self) -> None:
        """``session.flush()`` is called after the mutations."""
        row = _physiology_row(
            lt1={"hr": _state(value=150.0), "power": None, "pace": None},
        )
        repo, mock_session = _make_repo_with_row(row)

        await repo.update_in_place(
            row.athlete_id,
            lt1={"hr": _state(value=152.0), "power": None, "pace": None},
        )

        mock_session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_does_not_commit(self) -> None:
        """``session.commit()`` is NEVER called — the caller owns
        the commit boundary."""
        row = _physiology_row(
            lt1={"hr": _state(value=150.0), "power": None, "pace": None},
        )
        repo, mock_session = _make_repo_with_row(row)

        await repo.update_in_place(
            row.athlete_id,
            lt1={"hr": _state(value=152.0), "power": None, "pace": None},
        )

        mock_session.commit.assert_not_awaited()
        mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_flush_called_even_with_no_mutations(self) -> None:
        """``session.flush()`` is called even when every parameter
        is at its default (no column touched) — the ``updated_at``
        ``onupdate=`` hook still fires."""
        row = _physiology_row(
            lt1={"hr": _state(value=150.0), "power": None, "pace": None},
        )
        repo, mock_session = _make_repo_with_row(row)

        await repo.update_in_place(row.athlete_id)

        mock_session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# update_in_place — return value.
# ---------------------------------------------------------------------------


class TestUpdateInPlaceReturnValue:
    """``update_in_place`` returns the loaded row."""

    @pytest.mark.asyncio
    async def test_returns_same_row_instance(self) -> None:
        """The returned object is the same instance that was loaded
        by ``get_by_athlete_id`` — not a copy."""
        row = _physiology_row(
            lt1={"hr": _state(value=150.0), "power": None, "pace": None},
        )
        repo, _ = _make_repo_with_row(row)

        result = await repo.update_in_place(row.athlete_id)

        assert result is row


# ---------------------------------------------------------------------------
# update_in_place — no row exists.
# ---------------------------------------------------------------------------


class TestUpdateInPlaceNoRow:
    """``update_in_place`` raises ``RuntimeError`` when no row exists
    for the athlete."""

    @pytest.mark.asyncio
    async def test_raises_runtime_error_when_no_row(self) -> None:
        """A missing row raises ``RuntimeError`` with the expected
        message."""
        repo, _ = _make_repo_without_row()
        athlete_id = uuid.uuid4()

        with pytest.raises(RuntimeError) as exc_info:
            await repo.update_in_place(
                athlete_id,
                lt1={"hr": _state(value=150.0), "power": None, "pace": None},
            )

        assert (
            str(exc_info.value)
            == f"no AthletePhysiology row for athlete {athlete_id}"
        )

    @pytest.mark.asyncio
    async def test_no_flush_when_no_row(self) -> None:
        """``session.flush()`` is NOT called when the row is missing."""
        repo, mock_session = _make_repo_without_row()

        with pytest.raises(RuntimeError):
            await repo.update_in_place(
                uuid.uuid4(),
                lt1={"hr": _state(value=150.0), "power": None, "pace": None},
            )

        mock_session.flush.assert_not_awaited()
        mock_session.flush.assert_not_called()


# ---------------------------------------------------------------------------
# update_in_place — sentinel identity.
# ---------------------------------------------------------------------------


class TestUpdateInPlaceSentinelIdentity:
    """The ``UNSET_SENTINEL`` is an identity-checked object — a
    different ``object()`` instance is NOT the sentinel."""

    @pytest.mark.asyncio
    async def test_unset_sentinel_explicitly_passed_is_no_op(self) -> None:
        """Passing ``UNSET_SENTINEL`` explicitly is equivalent to
        not passing the argument — the column is unchanged."""
        original_cp = _state(value=260.0)
        row = _physiology_row(cp=original_cp)
        repo, _ = _make_repo_with_row(row)

        result = await repo.update_in_place(
            row.athlete_id, cp=UNSET_SENTINEL
        )

        assert result.cp == original_cp

    @pytest.mark.asyncio
    async def test_different_object_instance_is_not_sentinel(self) -> None:
        """A different ``object()`` instance is NOT the sentinel —
        the code's ``is not _UNSET`` check fails and the mutation
        branch executes (which then raises ``TypeError`` because
        ``object()`` is not a Mapping)."""
        row = _physiology_row(cp=_state(value=260.0))
        repo, _ = _make_repo_with_row(row)
        fake_sentinel = object()

        with pytest.raises(TypeError):
            await repo.update_in_place(row.athlete_id, cp=fake_sentinel)
