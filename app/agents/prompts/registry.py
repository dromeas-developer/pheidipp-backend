from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class PromptRecord:
    version: str
    system_prompt: str
    max_output_tokens: int
    deprecated: bool = False
    deprecation_note: Optional[str] = None


class PromptRegistry:
    _registry: dict[str, dict[str, PromptRecord]] = {}

    @classmethod
    def register(cls, agent: str, record: PromptRecord) -> None:
        if agent not in cls._registry:
            cls._registry[agent] = {}
        if record.version in cls._registry[agent]:
            raise ValueError(
                f"Prompt version '{record.version}' already registered for agent '{agent}'"
            )
        cls._registry[agent][record.version] = record

    @classmethod
    def get(cls, agent: str, version: str) -> PromptRecord:
        if agent not in cls._registry:
            raise KeyError(f"Agent '{agent}' not found in registry")
        if version not in cls._registry[agent]:
            raise KeyError(f"Version '{version}' not found for agent '{agent}'")
        return cls._registry[agent][version]

    @classmethod
    def current(cls, agent: str) -> PromptRecord:
        version = CURRENT_VERSIONS.get(agent)
        if version is None:
            raise KeyError(f"No current version defined for agent '{agent}'")
        return cls.get(agent, version)


CURRENT_VERSIONS: dict[str, str] = {
    "first_message": "v1"
}

# Import to trigger registration
from app.agents.prompts import first_message_v1  # noqa: E402, F401