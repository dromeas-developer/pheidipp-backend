"""PromptRegistry — versioned prompt template loader."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Dict

class PromptNotFoundError(LookupError):
    """No prompt file exists at the expected path."""

    def __init__(self, agent_name: str, version: str, path: Path) -> None:
        super().__init__(
            f"prompt not found for agent_name={agent_name!r} "
            f"version={version!r} at {path}"
        )
        self.agent_name = agent_name
        self.version = version
        self.path = path


class PromptRegistry:
    """Filesystem-backed prompt template registry with in-memory cache."""

    DEFAULT_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

    def __init__(self, prompts_dir: Path | None = None) -> None:
        self.prompts_dir: Path = prompts_dir or self.DEFAULT_PROMPTS_DIR
        self._cache: Dict[str, str] = {}
        self._cache_lock = threading.Lock()

    def get_prompt(self, agent_name: str, version: str) -> str:
        """Return the prompt body for ``{agent_name}_v{version}.md``."""
        cache_key = f"{agent_name}@{version}"
        with self._cache_lock:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
            content = self.load_prompt_from_disk(agent_name, version)
            self._cache[cache_key] = content
            return content

    def invalidate_cache(self) -> None:
        """Clear the in-memory cache."""
        with self._cache_lock:
            self._cache.clear()

    def load_prompt_from_disk(
        self, agent_name: str, version: str
    ) -> str:
        path = self.build_prompt_path(agent_name, version)
        if not path.is_file():
            raise PromptNotFoundError(
                agent_name=agent_name,
                version=version,
                path=path,
            )
        return path.read_text(encoding="utf-8")

    def build_prompt_path(
        self, agent_name: str, version: str
    ) -> Path:
        return self.prompts_dir / f"{agent_name}_{version}.md"

# Module-level singleton — used when no test override is provided.
# Production code shares one registry across the process so the
# filesystem read happens exactly once per (agent_name, version).

_default_registry: PromptRegistry | None = None
_default_registry_lock = threading.Lock()

def get_default_prompt_registry() -> PromptRegistry:
    """Return the process-wide default :class:`PromptRegistry`."""
    global _default_registry
    if _default_registry is None:
        with _default_registry_lock:
            if _default_registry is None:
                _default_registry = PromptRegistry()
    return _default_registry

def reset_default_prompt_registry() -> None:
    """Test helper — drop the process-wide default registry."""
    global _default_registry
    with _default_registry_lock:
        _default_registry = None

# Sentinel so the bare import does not look unused to linters.
_ = asyncio
