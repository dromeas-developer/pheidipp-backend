# GenerationEvent — LLM API Call Audit Log

## Purpose
- Records every LLM API call attempt, success or failure
- The primary operational observability primitive for the coaching layer
- Enables cost monitoring, quality tracking, prompt version analysis, and failure alerting

## TypeScript Schema

```typescript
type GenerationEvent = {
  id: string                    // UUID, PK
  athlete_id: string            // UUID, FK → Athlete
  agent_name: string            // e.g. 'first_message_agent', 'post_workout_agent'
  prompt_version: string        // version string from PromptRegistry
  trigger_context: string       // what caused this generation
  input_token_count: number
  output_token_count: number
  latency_ms: number
  success: boolean
  failure_reason: string | null // null on success; error type on failure
  created_at: string            // ISO 8601
}
```

## Invariants
- **Every LLM call writes a GenerationEvent, whether successful or not.** A `CoachingMessage` created without a corresponding `GenerationEvent` indicates an instrumentation failure.
- `failure_reason` is never null when `success = false`.
- Records are never modified after creation.
- `input_token_count` and `output_token_count` are required even on failure — capture whatever was available before failure.
- `agent_name` matches the class name of the agent that made the call.

## Events
None produced or consumed. `GenerationEvent` is a terminal write — nothing downstream reacts to it.

## APIs

```yaml
# No public API for GenerationEvent — operational use only

# Internal admin/observability:
GET /internal/generation-events
Query:
  agent_name?: string
  success?: boolean
  from?: datetime
  to?: datetime
  athlete_id?: UUID
Response: 200
  events: GenerationEventResponse[]
Auth: Internal service token only
```

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `generation_events` table | append-only | eventual (written async) | 90 days operational; archived to cold storage after |

Index: `(athlete_id, created_at DESC)` for per-athlete audit.
Index: `(agent_name, created_at DESC)` for per-agent monitoring.
Index: `(success, created_at DESC)` for failure rate dashboards.

## Mutation Rules
| Layer | Read | Write | Delete |
|---|---|---|---|
| API | Internal only | No | No |
| Service | Yes (monitoring) | insert() only | No |
| Repository | Yes | insert() only | No |

## Runtime Ownership
Owns:
- LLM call audit records
- Operational cost and performance data

Does Not Own:
- CoachingMessage content → `01-entities/coaching-message.md`
- Prompt content → `03-agents/` (PromptRegistry)

## Failure Semantics
- If writing the `GenerationEvent` itself fails (DB unavailable), the error is logged to the application log and the LLM response is not discarded. `GenerationEvent` write failure never blocks the `CoachingMessage` write.

## Performance Constraints
- `insert()`: p95 < 50ms (async write; does not block API response)

## Observability
This entity IS the observability primitive. Dashboards built from it:
- Cost per agent per day (sum of `input_token_count + output_token_count` by `agent_name`)
- Success rate by agent
- p50/p95/p99 latency by agent
- Failure type distribution (`failure_reason`)
- Prompt version migration tracking (`prompt_version` distribution over time)
