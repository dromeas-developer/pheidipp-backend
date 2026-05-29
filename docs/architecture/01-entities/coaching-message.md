# CoachingMessage — LLM-Generated Message to the Athlete

## Purpose
- Stores every message the coach sends to the athlete, regardless of trigger
- The persistent record of the coaching relationship
- Always linked to the TwinState that produced it

## TypeScript Schema

```typescript
type MessageType =
  | 'first_message'        // onboarding; one per athlete per block
  | 'post_workout'         // after session analysis; one per activity
  | 'wellness_alert'       // proactive wellness pattern detection
  | 'phase_transition'     // plan moves to a new phase
  | 'plan_regeneration'    // plan was restructured
  | 'confidence_upgrade'   // twin moved from low→medium or medium→high
  | 'cycle_check_in'       // prompt to log next cycle start (female athletes)
  | 'weekly_summary'       // optional weekly review (future)

type CoachingMessage = {
  id: string                    // UUID, PK
  athlete_id: string            // UUID, FK → Athlete
  twin_state_id: string         // UUID, FK → TwinState (active at generation)
  activity_id: string | null    // UUID, FK → Activity; set for post_workout only
  message_type: MessageType
  content: string               // the plain-text message; no markdown
  prompt_version: string        // version string of the prompt used
  generated_at: string          // ISO 8601
}
```

## Content Rules

All content must comply with the coach voice rules in `vision/coach/voice-and-format.md`:
- Three natural paragraphs (post_workout, first_message)
- No bullets, headers, or emojis
- No raw numbers without coaching context
- No acronyms without explanation
- No generic encouragement
- Plain English throughout

Proactive messages (wellness_alert, phase_transition, etc.) are typically one paragraph.

## Message Type Constraints

| Type | Trigger | One-per? | activity_id |
|---|---|---|---|
| `first_message` | Onboarding complete | One per block | null |
| `post_workout` | Activity analysed | One per activity | Required |
| `wellness_alert` | Sustained AMBER/RED (no alert in 5 days) | Rate-limited | null |
| `phase_transition` | First day of new plan phase | One per phase | null |
| `plan_regeneration` | Plan superseded | One per regeneration | null |
| `confidence_upgrade` | Confidence level increased | One per transition | null |
| `cycle_check_in` | ~21 days since last cycle log | Rate-limited (7 days) | null |

## Invariants
- `content` is never modified after creation. Messages are immutable.
- `first_message` — only one per athlete per active block. A second call to the generation endpoint returns 409.
- `post_workout` — only one per `activity_id`. Idempotent: second call returns existing message.
- Proactive messages have frequency guards enforced at the service layer (not DB constraints).
- Every message creation is preceded by a `GenerationEvent` record. A `CoachingMessage` without a corresponding `GenerationEvent` indicates a recording failure — monitored as an alert.

## Events

### Produced
| Event | Trigger | Version | Payload |
|---|---|---|---|
| `coaching_message_generated` | Message inserted | v1 | `{message_id, message_type, generation_event_id, prompt_version}` |

### Consumed
None.

## APIs

```yaml
GET /athletes/{athlete_id}/coach/messages
Query:
  message_type?: MessageType
  limit?: number (default 20)
  offset?: number
Response: 200
  messages: CoachingMessageResponse[]
  total: number
Auth: Bearer JWT, require_self

GET /athletes/{athlete_id}/coach/messages/{message_id}
Response: 200
  message: CoachingMessageResponse
Auth: Bearer JWT, require_self

POST /athletes/{athlete_id}/coach/first-message
Response: 201 | 409 (if already exists for this block)
  message: CoachingMessageResponse
Auth: Bearer JWT, require_self

POST /athletes/{athlete_id}/activities/{activity_id}/analyse
Response: 201 | 200 (idempotent)
  message: CoachingMessageResponse
Auth: Bearer JWT, require_self
```

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `coaching_messages` table | append-only | strong | indefinite |

Index: `(athlete_id, generated_at DESC)` for message feed.
Index: `(athlete_id, message_type, generated_at DESC)` for frequency guard queries.

## Mutation Rules
| Layer | Read | Write | Delete |
|---|---|---|---|
| API | Yes | Via agent endpoints | No |
| Service | Yes | insert() only | No |
| Repository | Yes | insert() only | No |

## Runtime Ownership
Owns:
- Persistent message storage
- Message feed for the athlete

Does Not Own:
- Message content generation → `03-agents/`
- Frequency guards → `03-agents/` (service layer)
- GenerationEvent logging → `01-entities/generation-event.md`

## Failure Semantics
- Agent failure → `GenerationEvent` written with success=false; no `CoachingMessage` created; 503 to caller
- Duplicate first_message request → 409 with the existing message_id in the response

## Performance Constraints
- `GET /coach/messages`: p95 < 100ms
- `GET /coach/messages/{id}`: p95 < 30ms

## Observability
Metrics:
- `coaching_message.generated.total`: by message_type
- `coaching_message.generation.success_rate`: by agent
- `coaching_message.generation.latency_ms`: by agent
Logs:
- `coaching_message.generated`: athlete_id, message_type, prompt_version, input_tokens, output_tokens
- `coaching_message.generation.failed`: athlete_id, message_type, failure_reason
