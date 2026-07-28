import uuid
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.enums import Sex
from app.schemas.auth import (
    AuthResponse,
    AthleteResponse,
    RegisterProfileIn,
    RegisterRequest,
    TokenPairResponse,
)


class TestRegisterPasswordValidation:
    def test_register_password_blank_whitespace_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(
                email="athlete@example.com",
                password="        ",
                profile=RegisterProfileIn(
                    date_of_birth=date(1990, 1, 15),
                    sex=Sex.MALE,
                    height_cm=180,
                ),
            )

        errors = exc_info.value.errors()
        assert any(
            "password must not be blank or whitespace-only" in e["msg"] for e in errors
        )


class TestTokenHashExclusion:
    def test_auth_response_excludes_token_hash(self):
        response = AuthResponse(
            athlete=AthleteResponse(
                id=uuid.uuid4(),
                email="athlete@example.com",
                onboarding_complete=False,
                created_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
            ),
            access_token="access-token-value",
            refresh_token="refresh-token-value",
            access_token_expires_in=900,
            refresh_token_expires_in=2592000,
        )
        data = response.model_dump()
        assert "token_hash" not in data
        assert "hashed_password" not in data

    def test_token_pair_response_excludes_token_hash(self):
        response = TokenPairResponse(
            access_token="access-token-value",
            refresh_token="refresh-token-value",
            access_token_expires_in=900,
            refresh_token_expires_in=2592000,
        )
        data = response.model_dump()
        assert "token_hash" not in data
        assert "hashed_password" not in data
