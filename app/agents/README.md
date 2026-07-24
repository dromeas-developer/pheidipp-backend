# app/agents/

## Purpose
LangGraph-style agent DAGs that orchestrate LLM calls for specific coaching workflows. Each agent owns its prompt assembly, LLM invocation, and result persistence within a caller-provided transaction. Agents flush writes but never commit — the caller (route handler or worker) owns the commit boundary.

## Contents
### Post-Workout
| File | Responsibility |
|---|---|
| `post_workout_agent.py` | `PostWorkoutAgent` — idempotent post-workout coach message generation with compliance-driven context and GenerationEvent audit logging |

### Workout Generation
| File | Responsibility |
|---|---|
| `workout_generation_agent.py` | `WorkoutGenerationAgent` — idempotent day-of workout generation with LLM step synthesis and GenerationEvent audit |

### Coach Onboarding
| File | Responsibility |
|---|---|
| `first_message_agent.py` | `FirstMessageAgent` — idempotent onboarding coach message generation with context-budget enforcement |

## Architecture Notes
- All agent classes accept repositories and services via constructor injection, receive `AsyncSession` directly, and never create sessions or engines themselves.
- Idempotency is enforced at the agent level: calling `generate` twice for the same input key returns the existing result without LLM invocation.
- Every LLM call writes a `GenerationEvent` (success or failure) to the audit log within the same transaction.
- LiteLLM proxy access via OpenAI-compatible client — all agents use `openai.AsyncOpenAI` pointed at the proxy URL, never direct provider SDKs.

## Cross-References
- [ADR-007: LLM Provider Gateway](../../docs/architecture/adr/ADR-007-llm-provider-gateway.md) — LiteLLM proxy as sole LLM access point
