"""Unit tests for coach message enums."""

import enum

import pytest

from app.models.enums import MessageType, GenerationOutcome


class TestMessageType:
    """Tests for MessageType enum."""

    def test_is_string_enum(self):
        """Verify MessageType is a string enum."""
        assert issubclass(MessageType, str)
        assert issubclass(MessageType, enum.Enum)

    def test_expected_values(self):
        """Verify MessageType has all expected values."""
        expected = {
            "first_message",
            "daily_briefing",
            "post_workout",
            "weekly_review",
            "recovery_alert",
            "phase_transition",
        }
        actual = {m.value for m in MessageType}
        assert actual == expected

    def test_each_value_is_string(self):
        """Verify each MessageType value is a string."""
        for member in MessageType:
            assert isinstance(member.value, str)


class TestGenerationOutcome:
    """Tests for GenerationOutcome enum."""

    def test_is_string_enum(self):
        """Verify GenerationOutcome is a string enum."""
        assert issubclass(GenerationOutcome, str)
        assert issubclass(GenerationOutcome, enum.Enum)

    def test_expected_values(self):
        """Verify GenerationOutcome has all expected values."""
        expected = {
            "success",
            "timeout",
            "provider_error",
            "rate_limited",
            "safety_refusal",
            "malformed",
            "missing_data",
            "internal_error",
        }
        actual = {m.value for m in GenerationOutcome}
        assert actual == expected

    def test_each_value_is_string(self):
        """Verify each GenerationOutcome value is a string."""
        for member in GenerationOutcome:
            assert isinstance(member.value, str)