import uuid
from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.auth_errors import InvalidCredentialsError, InvalidRefreshTokenError
from app.services.auth_service import AuthService


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def mock_token_service() -> MagicMock:
    svc = MagicMock()
    svc.issue_access_token.return_value = (
        "access-token-xyz",
        datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    svc.refresh_expiry.return_value = datetime(2026, 8, 25, tzinfo=timezone.utc)
    return svc


@pytest.fixture
def mock_password_hasher() -> MagicMock:
    hasher = MagicMock()
    hasher.hash.return_value = "$2b$12$hashedpasswordvaluehere1234567890"
    hasher.verify.return_value = True
    return hasher


@pytest.fixture
def auth_service(
    mock_session: Any,
    mock_token_service: Any,
    mock_password_hasher: Any,
) -> AuthService:
    return AuthService(
        session=mock_session,
        token_service=mock_token_service,
        password_hasher=mock_password_hasher,
    )


def _mock_repositories(
    auth_service: Any,
    overrides: dict[str, Any] | None = None,
) -> None:
    auth_service.athletes = MagicMock()
    auth_service.athletes.add = AsyncMock()
    auth_service.athletes.get_by_id = AsyncMock()
    auth_service.auths = MagicMock()
    auth_service.auths.add = AsyncMock()
    auth_service.auths.get_email_auth_by_normalized_email = AsyncMock()
    auth_service.auths.touch_last_login = AsyncMock()
    auth_service.profiles = MagicMock()
    auth_service.profiles.add = AsyncMock()
    auth_service.refresh_tokens = MagicMock()
    auth_service.refresh_tokens.add = AsyncMock()
    auth_service.refresh_tokens.get_by_token_hash = AsyncMock()
    auth_service.events = MagicMock()
    auth_service.events.publish = AsyncMock()
    if overrides:
        for k, v in overrides.items():
            parts = k.split(".")
            target = auth_service
            for part in parts[:-1]:
                target = getattr(target, part)
            setattr(target, parts[-1], v)


class TestRegister:
    async def test_register_creates_athlete_auth_profile_token_atomically(
        self, auth_service: Any, mock_session: AsyncMock
    ) -> None:
        _mock_repositories(auth_service)
        expected_athlete_id = uuid.uuid4()

        async def _mock_athletes_add(athlete: Any) -> Any:
            athlete.id = expected_athlete_id
            return athlete

        auth_service.athletes.add = AsyncMock(side_effect=_mock_athletes_add)
        auth_service.auths.add.return_value = MagicMock()
        auth_service.profiles.add.return_value = MagicMock()
        auth_service.refresh_tokens.add.return_value = MagicMock()

        result = await auth_service.register(
            email="athlete@example.com",
            password="validpass123",
            date_of_birth=date(1990, 1, 15),
            sex="male",
            height_cm=180,
        )

        auth_service.athletes.add.assert_called_once()
        auth_service.auths.add.assert_called_once()
        auth_service.profiles.add.assert_called_once()
        auth_service.refresh_tokens.add.assert_called_once()
        auth_service.events.publish.assert_called_once()
        mock_session.commit.assert_called_once()
        assert result.athlete_id == expected_athlete_id

    async def test_register_rollback_on_mid_transaction_failure(
        self, auth_service: Any, mock_session: AsyncMock
    ) -> None:
        _mock_repositories(auth_service)
        mock_athlete = MagicMock()
        mock_athlete.id = uuid.uuid4()
        auth_service.athletes.add.return_value = mock_athlete
        auth_service.auths.add = AsyncMock(
            side_effect=RuntimeError("mid-transaction failure")
        )

        with pytest.raises(RuntimeError, match="mid-transaction failure"):
            await auth_service.register(
                email="athlete@example.com",
                password="validpass123",
                date_of_birth=date(1990, 1, 15),
                sex="male",
                height_cm=180,
            )

        mock_session.commit.assert_not_called()


class TestLogin:
    async def test_login_successful_returns_token_pair(
        self,
        auth_service: Any,
        mock_session: AsyncMock,
        mock_password_hasher: MagicMock,
    ) -> None:
        _mock_repositories(auth_service)
        mock_auth_record = MagicMock()
        mock_auth_record.hashed_password = "$2b$12$hashedvalue"
        mock_auth_record.athlete_id = uuid.uuid4()
        auth_service.auths.get_email_auth_by_normalized_email.return_value = (
            mock_auth_record
        )
        mock_password_hasher.verify.return_value = True
        mock_athlete = MagicMock()
        mock_athlete.id = mock_auth_record.athlete_id
        mock_athlete.email = "athlete@example.com"
        mock_athlete.onboarding_complete = False
        mock_athlete.created_at = datetime(2026, 7, 25, tzinfo=timezone.utc)
        auth_service.athletes.get_by_id.return_value = mock_athlete

        result = await auth_service.login(
            email="athlete@example.com", password="validpass123"
        )

        auth_service.events.publish.assert_called_once()
        mock_session.commit.assert_called_once()
        assert result.athlete_id == mock_athlete.id

    async def test_login_wrong_password_returns_401(
        self, auth_service: Any, mock_password_hasher: MagicMock
    ) -> None:
        _mock_repositories(auth_service)
        mock_auth_record = MagicMock()
        mock_auth_record.hashed_password = "$2b$12$hashedvalue"
        auth_service.auths.get_email_auth_by_normalized_email.return_value = (
            mock_auth_record
        )
        mock_password_hasher.verify.return_value = False

        with pytest.raises(InvalidCredentialsError, match="invalid credentials"):
            await auth_service.login(
                email="athlete@example.com", password="wrongpassword"
            )

        auth_service.events.publish.assert_not_called()

    async def test_login_nonexistent_email_returns_401_constant_time(
        self, auth_service: Any, mock_password_hasher: MagicMock
    ) -> None:
        _mock_repositories(auth_service)
        auth_service.auths.get_email_auth_by_normalized_email.return_value = None

        with pytest.raises(InvalidCredentialsError, match="invalid credentials"):
            await auth_service.login(
                email="nosuchuser@example.com", password="anypassword"
            )

        mock_password_hasher.verify.assert_called_once()
        auth_service.events.publish.assert_not_called()


class TestRefreshToken:
    async def test_refresh_valid_token_rotates_atomically(
        self, auth_service: Any, mock_session: AsyncMock, mock_token_service: MagicMock
    ) -> None:
        _mock_repositories(auth_service)
        expected_token_id = uuid.uuid4()

        async def _mock_refresh_tokens_add(token: Any) -> Any:
            token.id = expected_token_id
            return token

        auth_service.refresh_tokens.add = AsyncMock(
            side_effect=_mock_refresh_tokens_add
        )
        existing_token = MagicMock()
        existing_token.athlete_id = uuid.uuid4()
        existing_token.revoked_at = None
        existing_token.expires_at = datetime(2026, 8, 25, tzinfo=timezone.utc)
        auth_service.refresh_tokens.get_by_token_hash.return_value = existing_token

        result = await auth_service.rotate_refresh_token(
            raw_refresh_token="valid-raw-token"
        )

        auth_service.refresh_tokens.add.assert_called_once()
        assert existing_token.revoked_at is not None
        assert existing_token.replaced_by_refresh_token_id == expected_token_id
        auth_service.events.publish.assert_called_once()
        mock_session.commit.assert_called_once()
        assert result.access_token == "access-token-xyz"
        assert result.refresh_token is not None

    async def test_refresh_old_token_invalid_after_rotation(
        self, auth_service: Any
    ) -> None:
        _mock_repositories(auth_service)
        existing_token = MagicMock()
        existing_token.revoked_at = datetime(2026, 7, 24, tzinfo=timezone.utc)
        existing_token.expires_at = datetime(2026, 8, 25, tzinfo=timezone.utc)
        auth_service.refresh_tokens.get_by_token_hash.return_value = existing_token

        with pytest.raises(InvalidRefreshTokenError, match="invalid refresh token"):
            await auth_service.rotate_refresh_token(
                raw_refresh_token="old-revoked-token"
            )

        auth_service.refresh_tokens.add.assert_not_called()

    async def test_refresh_expired_token_rejected(self, auth_service: Any) -> None:
        _mock_repositories(auth_service)
        existing_token = MagicMock()
        existing_token.revoked_at = None
        existing_token.expires_at = datetime(2026, 7, 1, tzinfo=timezone.utc)
        auth_service.refresh_tokens.get_by_token_hash.return_value = existing_token

        with pytest.raises(InvalidRefreshTokenError, match="invalid refresh token"):
            await auth_service.rotate_refresh_token(raw_refresh_token="expired-token")

        auth_service.refresh_tokens.add.assert_not_called()

    async def test_refresh_unknown_token_rejected(self, auth_service: Any) -> None:
        _mock_repositories(auth_service)
        auth_service.refresh_tokens.get_by_token_hash.return_value = None

        with pytest.raises(InvalidRefreshTokenError, match="invalid refresh token"):
            await auth_service.rotate_refresh_token(
                raw_refresh_token="nonexistent-hash"
            )

        auth_service.refresh_tokens.add.assert_not_called()

    async def test_refresh_rotation_atomicity_rollback(
        self, auth_service: Any, mock_session: AsyncMock
    ) -> None:
        _mock_repositories(auth_service)
        existing_token = MagicMock()
        existing_token.athlete_id = uuid.uuid4()
        existing_token.revoked_at = None
        existing_token.expires_at = datetime(2026, 8, 25, tzinfo=timezone.utc)
        auth_service.refresh_tokens.get_by_token_hash.return_value = existing_token
        mock_session.commit.side_effect = RuntimeError("commit failure")

        with pytest.raises(RuntimeError, match="commit failure"):
            await auth_service.rotate_refresh_token(raw_refresh_token="valid-raw-token")

        assert mock_session.commit.call_count == 1
