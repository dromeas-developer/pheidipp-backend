"""Integration tests for Training Blocks API endpoints."""

import uuid

import pytest
from httpx import AsyncClient


class TestGetBlockEndpoint:
    """Tests for GET /training-blocks/{block_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_block_returns_200(self, client: AsyncClient, test_db_session):
        """Test getting a block returns 200 with block data when found."""
        from tests.factories.athlete_factory import make_athlete
        from tests.factories.training_block_factory import make_training_block_full

        # Create athlete and block
        athlete = make_athlete()
        test_db_session.add(athlete)
        await test_db_session.commit()
        await test_db_session.refresh(athlete)

        block = make_training_block_full(athlete_id=athlete.id)
        test_db_session.add(block)
        await test_db_session.commit()
        await test_db_session.refresh(block)

        # Get block
        response = await client.get(f"/training-blocks/{block.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(block.id)
        assert data["athlete_id"] == str(athlete.id)
        assert data["goal_type"] == "race"
        assert data["status"] == "active"

    @pytest.mark.asyncio
    async def test_get_block_returns_404(self, client: AsyncClient):
        """Test getting nonexistent block returns 404."""
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/training-blocks/{fake_id}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Training block not found"


class TestUpdateBlockEndpoint:
    """Tests for PATCH /training-blocks/{block_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_block_status_to_completed(self, client: AsyncClient, test_db_session):
        """Test updating status to completed returns 200."""
        from tests.factories.athlete_factory import make_athlete
        from tests.factories.training_block_factory import make_training_block

        # Create athlete and block
        athlete = make_athlete()
        test_db_session.add(athlete)
        await test_db_session.commit()
        await test_db_session.refresh(athlete)

        block = make_training_block(athlete_id=athlete.id)
        test_db_session.add(block)
        await test_db_session.commit()
        await test_db_session.refresh(block)

        # Update block status
        update_payload = {"status": "completed"}
        response = await client.patch(f"/training-blocks/{block.id}", json=update_payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_update_block_status_to_abandoned(self, client: AsyncClient, test_db_session):
        """Test updating status to abandoned returns 200."""
        from tests.factories.athlete_factory import make_athlete
        from tests.factories.training_block_factory import make_training_block

        # Create athlete and block
        athlete = make_athlete()
        test_db_session.add(athlete)
        await test_db_session.commit()
        await test_db_session.refresh(athlete)

        block = make_training_block(athlete_id=athlete.id)
        test_db_session.add(block)
        await test_db_session.commit()
        await test_db_session.refresh(block)

        # Update block status
        update_payload = {"status": "abandoned"}
        response = await client.patch(f"/training-blocks/{block.id}", json=update_payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "abandoned"

    @pytest.mark.asyncio
    async def test_update_block_goal_event_date(self, client: AsyncClient, test_db_session):
        """Test updating goal_event_date returns 200."""
        from tests.factories.athlete_factory import make_athlete
        from tests.factories.training_block_factory import make_training_block

        # Create athlete and block
        athlete = make_athlete()
        test_db_session.add(athlete)
        await test_db_session.commit()
        await test_db_session.refresh(athlete)

        block = make_training_block(athlete_id=athlete.id)
        test_db_session.add(block)
        await test_db_session.commit()
        await test_db_session.refresh(block)

        # Update block goal_event_date
        update_payload = {"goal_event_date": "2024-06-01"}
        response = await client.patch(f"/training-blocks/{block.id}", json=update_payload)

        assert response.status_code == 200
        data = response.json()
        assert data["goal_event_date"] == "2024-06-01"

    @pytest.mark.asyncio
    async def test_update_block_goal_description(self, client: AsyncClient, test_db_session):
        """Test updating goal_description returns 200."""
        from tests.factories.athlete_factory import make_athlete
        from tests.factories.training_block_factory import make_training_block

        # Create athlete and block
        athlete = make_athlete()
        test_db_session.add(athlete)
        await test_db_session.commit()
        await test_db_session.refresh(athlete)

        block = make_training_block(athlete_id=athlete.id)
        test_db_session.add(block)
        await test_db_session.commit()
        await test_db_session.refresh(block)

        # Update block goal_description
        update_payload = {"goal_description": "Updated description"}
        response = await client.patch(f"/training-blocks/{block.id}", json=update_payload)

        assert response.status_code == 200
        data = response.json()
        assert data["goal_description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_update_block_partial(self, client: AsyncClient, test_db_session):
        """Test partial update with only one field returns 200."""
        from tests.factories.athlete_factory import make_athlete
        from tests.factories.training_block_factory import make_training_block_full

        # Create athlete and block
        athlete = make_athlete()
        test_db_session.add(athlete)
        await test_db_session.commit()
        await test_db_session.refresh(athlete)

        block = make_training_block_full(athlete_id=athlete.id)
        test_db_session.add(block)
        await test_db_session.commit()
        await test_db_session.refresh(block)

        original_goal_type = block.goal_type

        # Partial update
        update_payload = {"goal_description": "New description"}
        response = await client.patch(f"/training-blocks/{block.id}", json=update_payload)

        assert response.status_code == 200
        data = response.json()
        assert data["goal_description"] == "New description"
        # Other fields should remain unchanged
        assert data["goal_type"] == original_goal_type

    @pytest.mark.asyncio
    async def test_update_block_returns_404(self, client: AsyncClient):
        """Test updating nonexistent block returns 404."""
        fake_id = str(uuid.uuid4())
        update_payload = {"status": "completed"}
        response = await client.patch(f"/training-blocks/{fake_id}", json=update_payload)

        assert response.status_code == 404
        assert response.json()["detail"] == "Training block not found"

    @pytest.mark.asyncio
    async def test_update_block_rejects_immutable_fields(self, client: AsyncClient, test_db_session):
        """Test that semantic fields are NOT accepted by the update endpoint."""
        from tests.factories.athlete_factory import make_athlete
        from tests.factories.training_block_factory import make_training_block

        # Create athlete and block
        athlete = make_athlete()
        test_db_session.add(athlete)
        await test_db_session.commit()
        await test_db_session.refresh(athlete)

        block = make_training_block(athlete_id=athlete.id)
        test_db_session.add(block)
        await test_db_session.commit()
        await test_db_session.refresh(block)

        # Try to update immutable fields - these should be ignored (not in schema)
        # The schema only allows: status, goal_event_date, goal_description
        update_payload = {
            "goal_type": "fitness_improvement",  # Not allowed
            "goal_event_type": "half_marathon",  # Not allowed
            "custom_distance_km": 21.1,  # Not allowed
            "weekly_volume_hours": 15.0,  # Not allowed
            "weekly_volume_km": 100.0,  # Not allowed
            "fitness_level": 4,  # Not allowed
            "recent_injury": True,  # Not allowed
        }
        response = await client.patch(f"/training-blocks/{block.id}", json=update_payload)

        # Should still return 200 but ignore the immutable fields
        assert response.status_code == 200
        data = response.json()
        # These fields should remain unchanged (or default)
        assert data.get("goal_type") is None or data.get("goal_type") != "fitness_improvement"
        assert data.get("fitness_level") is None or data.get("fitness_level") != 4