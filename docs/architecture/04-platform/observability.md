# Observability — Metrics, Logging, and Alerting

## Purpose
- Defines the key metrics, log events, and alert conditions for operational health
- Complements the per-entity observability sections with system-wide dashboards

## Core Dashboards

### Ingestion Health
- `activity.ingested.total` by source (intervals_icu, manual_upload, manual_entry)
- `activity.calibration_eligible.rate` — % of ingested activities that are eligible
- `activity.fit_parse.failures` — corrupt or unreadable files
- `activity.ingestion.latency_ms` p50/p95/p99
- `twin_state.recalibrations.total` by trigger type

### Coaching Quality
- `coaching_message.generation.success_rate` by agent
- `coaching_message.generation.latency_ms` p50/p95/p99 by agent
- `generation_event.cost_per_day` — input + output tokens × price per token by agent
- `generation_event.prompt_version.distribution` — tracking prompt rollouts

### Twin Model Health
- `twin_state.confidence_distribution` — low/medium/high across athlete base
- `twin_state.confidence_upgrades.total` per week (leading indicator of onboarding success)
- `threshold_detection.update_rate` — % of calibration-eligible sessions producing threshold update
- `wellness_baseline.coverage_rate` — % athletes with ≥14 records in 28-day window
- `body_composition.coverage_rate` — % athletes with ≥12 body composition records (weight) in 28-day window

### Session Lifecycle
- `planned_session.skip_rate` by session_type (threshold, vo2max, long_run, easy_aerobic)
- `planned_session.miss_rate` by phase_label
- `planned_session.redistribution_rate`
- `workout_library.acceptance_rate` by session_type

### Auth Health
- `athlete.auth.registrations.total` by provider (email, google, strava)
- `athlete.auth.logins.total` by provider
- `athlete.auth.logins.failed.total` by provider
- `athlete.auth.methods.linked.total` by provider
- `athlete.auth.methods.removed.total` by provider
- `athlete.auth.oauth.refresh.failures.total` by provider

## Structured Log Events

All log events use structured JSON format. Key fields on every log:
`athlete_id`, `timestamp`, `service`, `event`, `duration_ms` (where applicable).

### Critical Path Events
```json
// Ingestion
{ "event": "activity.ingested", "athlete_id": "...", "source": "intervals_icu",
  "has_hr": true, "has_rr": false, "calibration_eligible": true, "duration_ms": 4200 }

{ "event": "activity.fit_parse.failed", "athlete_id": "...", "source": "manual_upload",
  "error_type": "corrupt_file" }

// Auth
{ "event": "athlete.registered", "athlete_id": "...", "auth_provider": "email", "has_password": true }

{ "event": "athlete.logged_in", "athlete_id": "...", "auth_provider": "google", "success": true }

{ "event": "auth_method.linked", "athlete_id": "...", "provider": "strava" }

{ "event": "auth_method.removed", "athlete_id": "...", "provider": "email" }

// Twin
{ "event": "twin_state.inserted", "athlete_id": "...", "trigger": "calibration",
  "confidence_level": "medium", "model_version": "v2-threshold-referenced" }

{ "event": "twin_state.confidence_upgraded", "athlete_id": "...", "from": "low", "to": "medium" }

// Coaching
{ "event": "coaching_message.generated", "athlete_id": "...", "agent": "post_workout_agent",
  "message_type": "post_workout", "input_tokens": 3240, "output_tokens": 412,
  "latency_ms": 5100, "prompt_version": "post_workout_v2_segments" }

{ "event": "coaching_message.generation.failed", "athlete_id": "...",
  "agent": "post_workout_agent", "failure_reason": "timeout", "retry_count": 2 }
```

## Alert Conditions

### P1 — Immediate Response (< 15 minutes)

| Condition | Threshold | Meaning |
|---|---|---|
| `activity.fit_parse.failures` spike | > 5 in 10 minutes | Object storage or parser issue |
| `coaching_message.generation.success_rate` drop | < 80% for any agent over 15 min | LLM API issue |
| DLQ non-empty | Any entry | Task failing after max retries |
| `twin_state.recalibration.failures` | > 3 consecutive per athlete | Twin update pipeline broken |

### P2 — Response Within 2 Hours

| Condition | Threshold | Meaning |
|---|---|---|
| `activity.ingestion.latency_ms` p95 | > 60s | Ingestion pipeline degraded |
| `activity.load_compute.failures` spike | > 10 in 15 minutes | Load computation systemic issue |
| `activity.load_compute.stuck.count` | > 0 | Activities in DLQ — manual intervention needed |
| `athlete.auth.logins.failed.total` | > 10 in 5 minutes | Possible brute force or credential stuffing |
| `athlete.auth.oauth.refresh.failures.total` | > 5 consecutive for same provider | OAuth provider token refresh broken |
| `intervals_icu.sync.failures` | > 5 consecutive for same athlete | Integration broken |
| `weather_forecast.fetch.success_rate` | < 70% over 1h | Weather API issue |
| Baseline computation not completing within batch window | > 2h | Nightly task hung |

### P3 — Next Business Day

| Condition | Threshold | Meaning |
|---|---|---|
| `twin_state.confidence_upgrades.total` | 0 per week for > 2 weeks | No athletes progressing |
| `planned_session.miss_rate` | > 30% over 7 days | Athletes not completing sessions |
| `generation_event.cost_per_day` | > 2× rolling 7-day average | Prompt regression or token bloat |
| `athlete.auth.methods.linked.total` | 0 new links per week | Auth linking feature unused |

## Tracing

Distributed traces for the critical path (FIT upload → coach message):

```
Span: ingestion_pipeline
  ├── fit_file_upload (object storage)
  ├── fit_parse
  ├── load_computation
  ├── calibration_eligibility
  ├── signal_cleaning
  └── twin_recalibration
       └── threshold_detection (if applicable)

Span: post_workout_pipeline
  ├── execution_analysis
  ├── comparable_session_lookup
  ├── objective_evaluation
  ├── context_assembly
  └── llm_call
```

Trace IDs propagate across async task boundaries via task payload.

## Cross-References
- Per-entity observability: individual files in `01-entities/`
- Failure handling and DLQ: `04-platform/failure-handling.md`
- GenerationEvent (primary coaching observability source): `01-entities/generation-event.md`
