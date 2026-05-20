"""Unit tests for PromptRegistry."""

import pytest

from app.agents.prompts.registry import PromptRegistry, PromptRecord, CURRENT_VERSIONS


class TestPromptRecord:
    """Tests for PromptRecord dataclass."""

    def test_is_frozen_dataclass(self):
        """Verify PromptRecord is a frozen dataclass."""
        record = PromptRecord(
            version="v1",
            system_prompt="Test prompt",
            max_output_tokens=600,
        )
        # Should not be able to modify after creation
        with pytest.raises(Exception):  # FrozenInstanceError
            record.version = "v2"

    def test_deprecated_defaults_to_false(self):
        """Verify deprecated=False by default."""
        record = PromptRecord(
            version="v1",
            system_prompt="Test prompt",
            max_output_tokens=600,
        )
        assert record.deprecated is False


class TestPromptRegistry:
    """Tests for PromptRegistry class."""

    def test_register_stores_prompt_record(self):
        """Verify register stores a PromptRecord under the given agent key."""
        record = PromptRecord(
            version="test_v1",
            system_prompt="Test prompt",
            max_output_tokens=100,
        )
        # Use a unique agent name to avoid conflicts with existing registrations
        PromptRegistry.register("test_agent", record)

        retrieved = PromptRegistry.get("test_agent", "test_v1")
        assert retrieved.version == "test_v1"
        assert retrieved.system_prompt == "Test prompt"
        assert retrieved.max_output_tokens == 100

    def test_register_raises_on_duplicate_version(self):
        """Verify register raises ValueError if the same version key is registered twice."""
        record1 = PromptRecord(
            version="dup_v1",
            system_prompt="First prompt",
            max_output_tokens=100,
        )
        record2 = PromptRecord(
            version="dup_v1",
            system_prompt="Second prompt",
            max_output_tokens=200,
        )

        PromptRegistry.register("test_dup_agent", record1)

        with pytest.raises(ValueError, match="already registered"):
            PromptRegistry.register("test_dup_agent", record2)

    def test_get_returns_correct_record(self):
        """Verify get(agent, version) returns the correct PromptRecord."""
        # The first_message v1 prompt should be registered
        record = PromptRegistry.get("first_message", "v1")
        assert record.version == "v1"
        assert record.system_prompt is not None
        assert record.max_output_tokens > 0

    def test_get_raises_key_error_for_unknown_version(self):
        """Verify get(agent, version) raises KeyError for unknown version."""
        with pytest.raises(KeyError, match="Version"):
            PromptRegistry.get("first_message", "nonexistent_version")

    def test_get_raises_key_error_for_unknown_agent(self):
        """Verify get(agent, version) raises KeyError for unknown agent."""
        with pytest.raises(KeyError, match="Agent"):
            PromptRegistry.get("nonexistent_agent", "v1")

    def test_current_resolves_via_current_versions_dict(self):
        """Verify current(agent) resolves via CURRENT_VERSIONS dict."""
        record = PromptRegistry.current("first_message")
        assert record.version == "v1"

    def test_current_raises_key_error_for_unknown_agent(self):
        """Verify current(agent) raises KeyError for unknown agent."""
        with pytest.raises(KeyError, match="No current version"):
            PromptRegistry.current("nonexistent_agent")


class TestCurrentVersions:
    """Tests for CURRENT_VERSIONS mapping."""

    def test_first_message_maps_to_v1(self):
        """Verify CURRENT_VERSIONS maps 'first_message' to 'v1'."""
        assert CURRENT_VERSIONS["first_message"] == "v1"