# AthleteIntegration — Third-Party Platform Connection

## Purpose
- Stores credentials and sync state for each connected training platform
- One record per athlete per platform; supports intervals.icu at launch, Garmin Connect planned

## TypeScript Schema

```typescript
type IntegrationPlatform = 'intervals_icu' | 'garmin_connect'

type AthleteIntegration = {
  athlete_id: string          // UUID, FK → Athlete
  platform: IntegrationPlatform
  credentials: string         // encrypted JSON; token storage; never returned by API
  last_synced_at: string | null  // ISO 8601; null if never synced
  sync_cursor: string | null     // opaque string; incremental sync position
  created_at: string
  updated_at: string
}
```

## Invariants
- Unique constraint on `(athlete_id, platform)`. One integration record per platform per athlete.
- `credentials` is encrypted at rest. Never returned by any API response.
- DELETE is supported — disconnecting removes credentials but leaves Activity records intact.
- `sync_cursor` is an opaque string owned by the sync task. It is updated atomically with `last_synced_at` after each successful sync batch.

## Events

### Produced
| Event | Trigger | Version | Payload |
|---|---|---|---|
| `integration_connected` | Record created | v1 | `{athlete_id, platform}` |
| `integration_disconnected` | Record deleted | v1 | `{athlete_id, platform}` |

### Consumed
None.

## APIs

```yaml
POST /athletes/{athlete_id}/integrations/intervals-icu
Request:
  token: string  # intervals.icu API token
Response: 201
  integration: AthleteIntegrationResponse  # credentials excluded
Auth: Bearer JWT, require_self

GET /athletes/{athlete_id}/integrations
Response: 200
  integrations: AthleteIntegrationResponse[]  # credentials excluded
Auth: Bearer JWT, require_self

DELETE /athletes/{athlete_id}/integrations/intervals-icu
Response: 204
Auth: Bearer JWT, require_self

POST /athletes/{athlete_id}/integrations/intervals-icu/sync
Response: 202 Accepted
  task_id: string
Auth: Bearer JWT, require_self
```

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `athlete_integrations` table | mutable (sync state updates) | strong | until deleted |

## Mutation Rules
| Layer | Read | Write | Delete |
|---|---|---|---|
| API | Yes (no credentials) | POST only | DELETE |
| Service | Yes (including credentials) | Yes | Yes |
| Repository | Yes | Yes | Yes |

## Runtime Ownership
Owns:
- Platform credentials and sync cursor state

Does Not Own:
- Sync task execution → `04-platform/async-pipeline.md`
- FIT file ingestion after sync → `01-entities/activity.md`
