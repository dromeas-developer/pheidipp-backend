# app/core/prompts/

## Purpose
Versioned prompt template files loaded at runtime by `app.core.prompt_registry.PromptRegistry`. Each file follows the naming convention `{agent_name}_v{version}.md` and contains the full system prompt for an LLM agent call. The registry caches these in memory for the process lifetime — hot-reload is intentionally unsupported.

## Contents
| File | Responsibility |
|---|---|
| `first_message_v1.md` | Onboarding coach message prompt: four-paragraph welcome drawing on athlete profile, observations, plan phases, and first-block preview |
| `post_workout_v1.md` | Post-workout coach prompt: three-paragraph session summary referencing compliance, load, and plan position |
| `workout_gen_v1.md` | Structured workout generation prompt: emits JSON step sequences (warmup → work/recovery → cooldown) with physiological intent, target types, and data-tier-aware numeric precision |

## Architecture Notes
- Filenames follow `{agent_name}_v{version}.md` — the agent layer resolves `"v1"` to the canonical filename; the registry does not enforce the version string format.
- Token accounting for prompts is the caller's job (`ContextBudgetService.estimate_tokens`); the registry returns raw content to keep coupling minimal.
- The `coaching_message_generated` event records `prompt_version` so a deploy that swaps a prompt template is auditable.

## Cross-References
- [app/core/README.md](../README.md) — describes `PromptRegistry`, the loader that consumes this folder
