"""Unit tests for ``PromptRegistry``.

Tests filesystem-backed prompt loading with in-memory cache:
- Loads prompt from filesystem
- Returns correct content
- Raises PromptNotFoundError when file missing
- Caches after first load
- Thread-safe caching

Reference plan: docs/implementation/phase-1/phase-1-5a-first-coach-message.md
"""

from __future__ import annotations

import threading
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest

from app.core.prompt_registry import (
    PromptNotFoundError,
    PromptRegistry,
    get_default_prompt_registry,
    reset_default_prompt_registry,
)


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_prompts_dir() -> Any:
    with TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def registry(temp_prompts_dir: Path) -> PromptRegistry:
    return PromptRegistry(prompts_dir=temp_prompts_dir)


@pytest.fixture
def registry_with_prompt(temp_prompts_dir: Path) -> tuple[PromptRegistry, Path]:
    """Registry with a first_message_v1.md file already written."""
    prompt_path = temp_prompts_dir / "first_message_v1.md"
    prompt_path.write_text("You are the coach. Write four paragraphs.", encoding="utf-8")
    return PromptRegistry(prompts_dir=temp_prompts_dir), prompt_path


# ---------------------------------------------------------------------------
# get_prompt — successful loading.
# ---------------------------------------------------------------------------


class TestGetPrompt:
    def test_returns_prompt_content(
        self, registry_with_prompt: tuple[PromptRegistry, Path]
    ) -> None:
        reg, _ = registry_with_prompt
        content = reg.get_prompt("first_message", "v1")
        assert content == "You are the coach. Write four paragraphs."

    def test_different_version_returns_different_content(
        self, registry_with_prompt: tuple[PromptRegistry, Path]
    ) -> None:
        reg, _ = registry_with_prompt
        # Write a second version
        v2_path = registry_with_prompt[1].parent / "first_message_v2.md"
        v2_path.write_text("You are the coach. Write five paragraphs.", encoding="utf-8")

        content_v1 = reg.get_prompt("first_message", "v1")
        content_v2 = reg.get_prompt("first_message", "v2")
        assert content_v1 != content_v2
        assert content_v2 == "You are the coach. Write five paragraphs."


# ---------------------------------------------------------------------------
# get_prompt — PromptNotFoundError.
# ---------------------------------------------------------------------------


class TestPromptNotFound:
    def test_raises_when_file_missing(self, registry: PromptRegistry) -> None:
        with pytest.raises(PromptNotFoundError) as exc_info:
            registry.get_prompt("nonexistent", "v1")
        assert exc_info.value.agent_name == "nonexistent"
        assert exc_info.value.version == "v1"

    def test_error_includes_path(self, registry: PromptRegistry) -> None:
        with pytest.raises(PromptNotFoundError) as exc_info:
            registry.get_prompt("first_message", "v9")
        assert exc_info.value.path.name == "first_message_v9.md"

    def test_raises_for_partial_match(self, registry: PromptRegistry) -> None:
        """Registry checks exact filename, not partial."""
        # Write first_message_v1.md only
        (registry._prompts_dir / "first_message_v1.md").write_text(
            "content", encoding="utf-8"
        )
        with pytest.raises(PromptNotFoundError):
            registry.get_prompt("first_message", "v2")  # v2 doesn't exist


# ---------------------------------------------------------------------------
# Caching behavior.
# ---------------------------------------------------------------------------


class TestCaching:
    def test_caches_after_first_load(
        self, registry_with_prompt: tuple[PromptRegistry, Path]
    ) -> None:
        reg, prompt_path = registry_with_prompt

        # First call loads from disk.
        content1 = reg.get_prompt("first_message", "v1")

        # Modify the file — cache should prevent changes.
        prompt_path.write_text("MODIFIED CONTENT", encoding="utf-8")

        # Second call returns cached content.
        content2 = reg.get_prompt("first_message", "v1")
        assert content2 == content1
        assert content2 != "MODIFIED CONTENT"

    def test_different_agent_version_combinations_independent(
        self, registry_with_prompt: tuple[PromptRegistry, Path]
    ) -> None:
        reg, _ = registry_with_prompt
        content1 = reg.get_prompt("first_message", "v1")

        # Add second agent/version
        (registry_with_prompt[1].parent / "workout_generation_v1.md").write_text(
            "workout prompt", encoding="utf-8"
        )
        content2 = reg.get_prompt("workout_generation", "v1")
        assert content2 == "workout prompt"
        # Original cache unaffected
        assert reg.get_prompt("first_message", "v1") == content1

    def test_invalidate_cache_clears_all(
        self, registry_with_prompt: tuple[PromptRegistry, Path]
    ) -> None:
        reg, prompt_path = registry_with_prompt
        reg.get_prompt("first_message", "v1")

        # Modify file and invalidate.
        prompt_path.write_text("NEW CONTENT", encoding="utf-8")
        reg.invalidate_cache()

        # Now returns new content.
        assert reg.get_prompt("first_message", "v1") == "NEW CONTENT"


# ---------------------------------------------------------------------------
# Thread-safety of cache.
# ---------------------------------------------------------------------------


class TestCacheThreadSafety:
    def test_concurrent_loads_same_content(
        self, registry_with_prompt: tuple[PromptRegistry, Path]
    ) -> None:
        reg, _ = registry_with_prompt
        results: list[str] = []
        errors: list[Exception] = []

        def load() -> None:
            try:
                results.append(reg.get_prompt("first_message", "v1"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=load) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(set(results)) == 1  # All return same content


# ---------------------------------------------------------------------------
# Default registry singleton.
# ---------------------------------------------------------------------------


class TestDefaultRegistry:
    def test_reset_clears_singleton(self) -> None:
        reset_default_prompt_registry()
        reg1 = get_default_prompt_registry()
        reset_default_prompt_registry()
        reg2 = get_default_prompt_registry()
        # Different instances after reset
        # (module-level cache was cleared)
        assert reg1 is not reg2

    def test_returns_same_instance_without_reset(self) -> None:
        reset_default_prompt_registry()
        reg1 = get_default_prompt_registry()
        reg2 = get_default_prompt_registry()
        assert reg1 is reg2


# ---------------------------------------------------------------------------
# Path building.
# ---------------------------------------------------------------------------


class TestPromptPathBuilding:
    def test_builds_correct_path(self, registry: PromptRegistry) -> None:
        path = registry._build_prompt_path("first_message", "v1")
        assert path.name == "first_message_v1.md"

    def test_version_embedded_in_filename(self, registry: PromptRegistry) -> None:
        path = registry._build_prompt_path("workout_generation", "v2")
        assert path.name == "workout_generation_v2.md"


# ---------------------------------------------------------------------------
# Prompt file existence check.
# ---------------------------------------------------------------------------


class TestPromptFileExistence:
    def test_is_file_checked_before_read(self, registry: PromptRegistry) -> None:
        # Directory exists but no file
        with pytest.raises(PromptNotFoundError):
            registry.get_prompt("missing", "v1")