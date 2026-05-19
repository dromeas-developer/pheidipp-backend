"""Integration tests for dependency factories in app/api/dependencies/services.py."""

import pytest
from unittest.mock import MagicMock, patch

from app.api.dependencies.services import (
    get_activity_service,
    get_wellness_service,
    get_fitness_service,
    get_athlete_service,
    get_athlete_profile_service,
    get_athlete_preferences_service,
    get_training_block_service,
    get_physiology_service,
)


class TestServiceDependencyFactories:
    """Tests for service dependency factories."""

    @pytest.mark.asyncio
    async def test_get_activity_service_returns_service_with_repositories(self):
        """Test get_activity_service returns ActivityService with non-null repositories."""
        from app.services.activity_service import ActivityService

        with patch("app.api.dependencies.services.get_db") as mock_get_db:
            mock_session = MagicMock()
            mock_get_db.return_value = mock_session

            service = await get_activity_service()

            assert isinstance(service, ActivityService)
            assert service.activity_repo is not None
            assert service.athlete_repo is not None

    @pytest.mark.asyncio
    async def test_get_wellness_service_returns_service_with_repositories(self):
        """Test get_wellness_service returns WellnessService with non-null repositories."""
        from app.services.wellness_service import WellnessService

        with patch("app.api.dependencies.services.get_db") as mock_get_db:
            mock_session = MagicMock()
            mock_get_db.return_value = mock_session

            service = await get_wellness_service()

            assert isinstance(service, WellnessService)
            assert service.wellness_repo is not None
            assert service.athlete_repo is not None

    @pytest.mark.asyncio
    async def test_get_fitness_service_returns_service_with_repositories(self):
        """Test get_fitness_service returns FitnessService with non-null repositories."""
        from app.services.fitness_service import FitnessService

        with patch("app.api.dependencies.services.get_db") as mock_get_db:
            mock_session = MagicMock()
            mock_get_db.return_value = mock_session

            service = await get_fitness_service()

            assert isinstance(service, FitnessService)
            assert service.fitness_repo is not None
            assert service.athlete_repo is not None

    @pytest.mark.asyncio
    async def test_get_athlete_service_returns_service_with_repositories(self):
        """Test get_athlete_service returns AthleteService with non-null repositories."""
        from app.services.athlete_service import AthleteService

        with patch("app.api.dependencies.services.get_db") as mock_get_db:
            mock_session = MagicMock()
            mock_get_db.return_value = mock_session

            service = await get_athlete_service()

            assert isinstance(service, AthleteService)
            assert service.athlete_repo is not None
            assert service.profile_repo is not None

    @pytest.mark.asyncio
    async def test_get_athlete_profile_service_returns_service_with_repository(self):
        """Test get_athlete_profile_service returns AthleteProfileService with non-null repository."""
        from app.services.athlete_profile_service import AthleteProfileService

        with patch("app.api.dependencies.services.get_db") as mock_get_db:
            mock_session = MagicMock()
            mock_get_db.return_value = mock_session

            service = await get_athlete_profile_service()

            assert isinstance(service, AthleteProfileService)
            assert service.profile_repo is not None

    def test_get_athlete_preferences_service_returns_service_with_repository(self):
        """Test get_athlete_preferences_service returns AthletePreferencesService with non-null repository."""
        from app.services.athlete_preferences_service import AthletePreferencesService

        with patch("app.api.dependencies.services.get_db") as mock_get_db:
            mock_session = MagicMock()
            mock_get_db.return_value = mock_session

            service = get_athlete_preferences_service()

            assert isinstance(service, AthletePreferencesService)
            assert service.repo is not None

    def test_get_training_block_service_returns_service_with_repository(self):
        """Test get_training_block_service returns TrainingBlockService with non-null repository."""
        from app.services.training_block_service import TrainingBlockService

        with patch("app.api.dependencies.services.get_db") as mock_get_db:
            mock_session = MagicMock()
            mock_get_db.return_value = mock_session

            service = get_training_block_service()

            assert isinstance(service, TrainingBlockService)
            assert service.repo is not None

    @pytest.mark.asyncio
    async def test_get_physiology_service_returns_service_with_repositories(self):
        """Test get_physiology_service returns PhysiologyService with non-null repositories."""
        from app.services.physiology_service import PhysiologyService

        with patch("app.api.dependencies.services.get_db") as mock_get_db:
            mock_session = MagicMock()
            mock_get_db.return_value = mock_session

            service = await get_physiology_service()

            assert isinstance(service, PhysiologyService)
            assert service.physiology_repo is not None
            assert service.athlete_repo is not None


class TestRouteFilesNoDirectRepositoryImports:
    """Tests that route files no longer import repositories directly."""

    def test_athletes_route_no_repository_imports(self):
        """Test app/api/routes/athletes.py has no imports of *Repository classes."""
        import app.api.routes.athletes as athletes_module

        # Check that no repository classes are imported
        repo_names = [name for name in dir(athletes_module) if "Repository" in name]
        assert len(repo_names) == 0, f"Found repository imports in athletes.py: {repo_names}"

    def test_activities_route_no_repository_imports(self):
        """Test app/api/routes/activities.py has no imports of *Repository classes."""
        import app.api.routes.activities as activities_module

        # Check that no repository classes are imported
        repo_names = [name for name in dir(activities_module) if "Repository" in name]
        assert len(repo_names) == 0, f"Found repository imports in activities.py: {repo_names}"

    def test_wellness_route_no_repository_imports(self):
        """Test app/api/routes/wellness.py has no imports of *Repository classes."""
        import app.api.routes.wellness as wellness_module

        # Check that no repository classes are imported
        repo_names = [name for name in dir(wellness_module) if "Repository" in name]
        assert len(repo_names) == 0, f"Found repository imports in wellness.py: {repo_names}"

    def test_fitness_route_no_repository_imports(self):
        """Test app/api/routes/fitness.py has no imports of *Repository classes."""
        import app.api.routes.fitness as fitness_module

        # Check that no repository classes are imported
        repo_names = [name for name in dir(fitness_module) if "Repository" in name]
        assert len(repo_names) == 0, f"Found repository imports in fitness.py: {repo_names}"

    def test_physiology_route_no_repository_imports(self):
        """Test app/api/routes/physiology.py has no imports of *Repository classes."""
        import app.api.routes.physiology as physiology_module

        # Check that no repository classes are imported
        repo_names = [name for name in dir(physiology_module) if "Repository" in name]
        assert len(repo_names) == 0, f"Found repository imports in physiology.py: {repo_names}"