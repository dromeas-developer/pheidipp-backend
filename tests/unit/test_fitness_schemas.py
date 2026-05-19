"""Unit tests for fitness schemas."""

import uuid
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.models.enums import DataSource
from app.schemas.fitness import (
    FitnessBase,
    FitnessCreate,
    FitnessUpdate,
    FitnessResponse,
    FitnessListParams,
    FitnessListResponse,
)


class TestFitnessBase:
    """Tests for FitnessBase schema."""

    def test_valid_construction_with_all_fields(self):
        """Test FitnessBase valid construction with all fields."""
        fitness = FitnessBase(
            metric_date=date(2024, 1, 15),
            tss=75.5,
            atl=42.0,
            ctl=65.0,
            tsb=23.0,
            source=DataSource.GARMIN,
        )
        assert fitness.metric_date == date(2024, 1, 15)
        assert fitness.tss == 75.5
        assert fitness.atl == 42.0
        assert fitness.ctl == 65.0
        assert fitness.tsb == 23.0
        assert fitness.source == DataSource.GARMIN

    def test_partial_construction_only_required_fields(self):
        """Test FitnessBase partial construction (only required fields)."""
        fitness = FitnessBase(
            metric_date=date(2024, 1, 15),
        )
        assert fitness.metric_date == date(2024, 1, 15)
        assert fitness.tss is None
        assert fitness.atl is None
        assert fitness.ctl is None
        assert fitness.tsb is None
        assert fitness.source == DataSource.MANUAL  # default

    def test_invalid_source_enum_rejection(self):
        """Test FitnessBase invalid source enum rejection."""
        with pytest.raises(ValidationError) as exc_info:
            FitnessBase(
                metric_date=date(2024, 1, 15),
                source="invalid_source",
            )
        assert "source" in str(exc_info.value)


class TestFitnessCreate:
    """Tests for FitnessCreate schema."""

    def test_valid_construction_including_athlete_id(self):
        """Test FitnessCreate valid construction including athlete_id."""
        athlete_id = uuid.uuid4()
        fitness = FitnessCreate(
            athlete_id=athlete_id,
            metric_date=date(2024, 1, 15),
            tss=75.5,
            atl=42.0,
            ctl=65.0,
            tsb=23.0,
            source=DataSource.GARMIN,
        )
        assert fitness.athlete_id == athlete_id
        assert fitness.metric_date == date(2024, 1, 15)
        assert fitness.tss == 75.5

    def test_missing_required_fields_rejection(self):
        """Test FitnessCreate missing required fields rejection."""
        with pytest.raises(ValidationError) as exc_info:
            FitnessCreate(
                tss=75.5,
            )
        errors = exc_info.value.errors()
        assert any("metric_date" in str(e["loc"]) for e in errors)
        assert any("athlete_id" in str(e["loc"]) for e in errors)


class TestFitnessUpdate:
    """Tests for FitnessUpdate schema."""

    def test_partial_update_construction(self):
        """Test FitnessUpdate partial update construction."""
        fitness = FitnessUpdate(
            metric_date=date(2024, 1, 15),
            tss=100.0,
        )
        assert fitness.metric_date == date(2024, 1, 15)
        assert fitness.tss == 100.0
        assert fitness.atl is None
        assert fitness.ctl is None
        assert fitness.tsb is None


class TestFitnessResponse:
    """Tests for FitnessResponse schema."""

    def test_valid_construction(self):
        """Test FitnessResponse valid construction."""
        athlete_id = uuid.uuid4()
        fitness = FitnessResponse(
            id=uuid.uuid4(),
            athlete_id=athlete_id,
            metric_date=date(2024, 1, 15),
            tss=75.5,
            atl=42.0,
            ctl=65.0,
            tsb=23.0,
            source=DataSource.GARMIN,
            created_at=datetime(2024, 1, 15, 10, 0, 0),
            updated_at=datetime(2024, 1, 15, 10, 0, 0),
        )
        assert fitness.id is not None
        assert fitness.athlete_id == athlete_id

    def test_from_attributes_validation(self):
        """Test FitnessResponse from_attributes validation using AthleteFitness model."""
        # Create a mock AthleteFitness model instance
        mock_model = MagicMock()
        mock_model.id = uuid.uuid4()
        mock_model.athlete_id = uuid.uuid4()
        mock_model.metric_date = date(2024, 1, 15)
        mock_model.tss = 75.5
        mock_model.atl = 42.0
        mock_model.ctl = 65.0
        mock_model.tsb = 23.0
        mock_model.source = DataSource.GARMIN
        mock_model.created_at = datetime(2024, 1, 15, 10, 0, 0)
        mock_model.updated_at = datetime(2024, 1, 15, 10, 0, 0)

        # Validate that the schema can be constructed from the model
        response = FitnessResponse.model_validate(mock_model)
        assert response.id == mock_model.id
        assert response.tss == 75.5


class TestFitnessListParams:
    """Tests for FitnessListParams schema."""

    def test_defaults(self):
        """Test FitnessListParams defaults."""
        params = FitnessListParams()
        assert params.date_from is None
        assert params.date_to is None
        assert params.limit == 50
        assert params.offset == 0

    def test_valid_limits(self):
        """Test FitnessListParams valid limits."""
        params = FitnessListParams(limit=100)
        assert params.limit == 100

        params = FitnessListParams(limit=1)
        assert params.limit == 1

    def test_invalid_limit_rejection(self):
        """Test FitnessListParams invalid limit rejection."""
        with pytest.raises(ValidationError) as exc_info:
            FitnessListParams(limit=0)
        assert "limit" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            FitnessListParams(limit=1001)
        assert "limit" in str(exc_info.value)


class TestFitnessListResponse:
    """Tests for FitnessListResponse schema."""

    def test_valid_construction(self):
        """Test FitnessListResponse valid construction."""
        athlete_id = uuid.uuid4()
        items = [
            FitnessResponse(
                id=uuid.uuid4(),
                athlete_id=athlete_id,
                metric_date=date(2024, 1, 15),
                source=DataSource.MANUAL,
                created_at=datetime(2024, 1, 15, 10, 0, 0),
                updated_at=datetime(2024, 1, 15, 10, 0, 0),
            ),
            FitnessResponse(
                id=uuid.uuid4(),
                athlete_id=athlete_id,
                metric_date=date(2024, 1, 16),
                source=DataSource.GARMIN,
                created_at=datetime(2024, 1, 16, 10, 0, 0),
                updated_at=datetime(2024, 1, 16, 10, 0, 0),
            ),
        ]
        response = FitnessListResponse(items=items, total=2)
        assert len(response.items) == 2
        assert response.total == 2