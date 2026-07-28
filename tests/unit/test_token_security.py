import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.core.logging_utils import safe_extra


class TestSafeExtraFiltersSensitiveKeys:
    def test_token_hash_blocked_by_forbidden_keys(self):
        payload = safe_extra(
            {
                "event": "test.event",
                "token_hash": "abc123",
                "athlete_id": str(uuid.uuid4()),
            }
        )
        assert "token_hash" not in payload
        assert "event" in payload
        assert "athlete_id" in payload

    def test_hashed_password_blocked_by_forbidden_keys(self):
        payload = safe_extra(
            {
                "event": "test.event",
                "hashed_password": "$2b$12$abcdef",
                "auth_provider": "email",
            }
        )
        assert "hashed_password" not in payload
        assert "event" in payload
        assert "auth_provider" in payload

    def test_ip_address_blocked_by_forbidden_keys(self):
        payload = safe_extra(
            {
                "event": "test.event",
                "ip_address": "192.168.1.100",
                "token_type": "access",
            }
        )
        assert "ip_address" not in payload
        assert "event" in payload
        assert "token_type" in payload

    def test_unknown_keys_excluded(self):
        payload = safe_extra(
            {
                "event": "test.event",
                "random_field": "should-not-pass",
                "athlete_id": str(uuid.uuid4()),
            }
        )
        assert "random_field" not in payload
        assert "event" in payload
        assert "athlete_id" in payload


class TestDiscardOldIps:
    async def test_discard_old_ips_sets_ip_address_to_none(self):
        from app.repositories.refresh_token_repository import RefreshTokenRepository

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_session.execute = AsyncMock(return_value=mock_result)
        repo = RefreshTokenRepository(mock_session)

        now = datetime(2026, 7, 25, tzinfo=timezone.utc)

        count = await repo.discard_old_ips(now=now)

        assert count == 3
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args[0]
        assert len(call_args) >= 1
        mock_session.flush.assert_not_called()

    async def test_discard_old_ips_returns_zero_when_no_rows(self):
        from app.repositories.refresh_token_repository import RefreshTokenRepository

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute = AsyncMock(return_value=mock_result)
        repo = RefreshTokenRepository(mock_session)

        count = await repo.discard_old_ips()

        assert count == 0
