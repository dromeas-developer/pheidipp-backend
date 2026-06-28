"""PromptRegistry — versioned prompt template loader.

Loads prompt templates from the filesystem and caches them in
memory. Filenames follow the convention ``{agent_name}_v{version}.md``
inside the prompts directory (default: ``app/core/prompts``).

Thread-safety: ``asyncio`` runs on a single event-loop thread per
process, so the in-memory cache needs no locking for concurrent
coroutines — the worst case is a duplicate filesystem read on cold
start, which is harmless and self-heals on first completion. The
module-level ``_load_prompt_from_disk`` helper is guarded by a
``threading.Lock`` so a multi-threaded caller (e.g. a sync worker
process) cannot race into two back-to-back ``read()`` calls for the
same path.

Caching strategy: prompts are read once on first access and held
until process restart. Hot-reload is intentionally NOT supported —
the ``coaching_message_generated`` event records
``prompt_version`` so a deploy that swaps a prompt template is
auditable, not a surprise.

The registry never enforces the version string format; the agent
layer is responsible for resolving ``"v1"`` to the canonical
filename. ``get_prompt`` raises :class:`PromptNotFoundError` when the
filesystem has no file at the expected path so the agent surfaces a
deterministic 5xx rather than failing mysteriously.

Token accounting: token estimation for prompts is the caller's job
(:class:`ContextBudgetService.estimate_tokens`); the registry
returns raw prompt content to keep coupling minimal.
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Dict


class PromptNotFoundError(LookupError):
    """No prompt file exists at the expected path.

    Raised by :meth:`PromptRegistry.get_prompt` when the agent_name +
    version combination resolves to a path that doesn't exist on
    disk. The agent maps this to a 503-generation-failed response —
    a missing prompt file is a deploy bug, not an athlete-facing one.
    """

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
        self._prompts_dir: Path = prompts_dir or self.DEFAULT_PROMPTS_DIR
        self._cache: Dict[str, str] = {}
        self._cache_lock = threading.Lock()

    def get_prompt(self, agent_name: str, version: str) -> str:
        """Return the prompt body for ``{agent_name}_v{version}.md``.

        On first access the file is loaded from disk and cached. The
        cache key is the ``(agent_name, version)`` pair expressed as
        ``"{agent_name}@{version}"`` so distinct agent/version
        combinations do not collide.

        Raises:
            PromptNotFoundError: the disk has no file at the
                canonical path.
        """
        cache_key = f"{agent_name}@{version}"
        with self._cache_lock:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
            content = self._load_prompt_from_disk(agent_name, version)
            self._cache[cache_key] = content
            return content

    def invalidate_cache(self) -> None:
        """Clear the in-memory cache.

        Intended for tests that swap prompt files at runtime — the
        production code path does not call this. Multi-thread-safe
        via the same lock that guards ``get_prompt``.
        """
        with self._cache_lock:
            self._cache.clear()

    def _load_prompt_from_disk(
        self, agent_name: str, version: str
    ) -> str:
        path = self._build_prompt_path(agent_name, version)
        if not path.is_file():
            raise PromptNotFoundError(
                agent_name=agent_name,
                version=version,
                path=path,
            )
        return path.read_text(encoding="utf-8")

    def _build_prompt_path(
        self, agent_name: str, version: str
    ) -> Path:
        return self._prompts_dir / f"{agent_name}_{version}.md"


# ---------------------------------------------------------------------------
# Module-level singleton — used when no test override is provided.
# Production code shares one registry across the process so the
# filesystem read happens exactly once per (agent_name, version).
# ---------------------------------------------------------------------------

_default_registry: PromptRegistry | None = None
_default_registry_lock = threading.Lock()


def get_default_prompt_registry() -> PromptRegistry:
    """Return the process-wide default :class:`PromptRegistry`.

    Lazy-initialised so test code that overrides ``prompts_dir`` via
    :class:`PromptRegistry` directly is unaffected. The lock keeps
    concurrent first-callers from racing into two ``Path`` allocations.
    """
    global _default_registry
    if _default_registry is None:
        with _default_registry_lock:
            if _default_registry is None:
                _default_registry = PromptRegistry()
    return _default_registry


def reset_default_prompt_registry() -> None:
    """Test helper — drop the process-wide default registry.

    Not for production use. The default registry is intentionally
    long-lived so the filesystem read happens once.
    """
    global _default_registry
    with _default_registry_lock:
        _default_registry = None


# Sentinel so the bare import does not look unused to linters.
_ = asyncio
