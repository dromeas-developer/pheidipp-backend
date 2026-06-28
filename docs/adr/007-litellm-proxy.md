---
id: ADR-007
status: accepted
tags: [llm, infrastructure, proxy, litellm]
supersedes: ~
superseded-by: ~
---

# ADR 007: All LLM Calls Route Through LiteLLM Proxy

## Rules
**Centralised LLM Access**: Every LLM API call in Pheidipp routes through the LiteLLM proxy server. No direct provider API calls are permitted.

**OpenAI-Compatible Client**: All agents use the OpenAI-compatible client SDK, configured with `LITELLM_BASE_URL` and `LITELLM_API_KEY` from environment.

**Model Abstraction**: Agents specify model names as logical identifiers (e.g., `cohere/command-a-plus`). The proxy handles provider-specific routing and API translation.

**Proxy as Infrastructure**: The LiteLLM proxy is a first-class infrastructure component. Agents do not implement provider-specific logic, retry handling, or message cleaning — the proxy owns this.

## Decision
All LLM API calls route through the LiteLLM proxy server rather than making direct calls to provider APIs (OpenAI, Anthropic, Cohere, etc.). This centralises provider abstraction, retry logic, rate limiting, observability, and message history cleaning. The proxy is configured via `litellm_proxy/pheidipp_litellm_config.yaml` and is accessible at `http://litellm:4000` (Docker service name from `docker-compose.yml`).

## Rationale
- **Provider abstraction**: Switching from Cohere to Anthropic or adding a new provider requires only config changes, not code changes. The proxy's OpenAI-compatible API means agents never need provider-specific SDKs.

- **Cross-provider retry and rate limiting**: The proxy implements exponential backoff, circuit breakers, and per-model cooldowns (configured in `pheidipp_litellm_config.yaml`). Implementing this per-provider in application code would be error-prone and duplicated.

- **Message history cleaning**: Different providers have different expectations for message format. Cohere rejects empty assistant messages with tool calls; DeepSeek R1 returns reasoning tokens that pollute subsequent turns. The proxy's `MessageHistoryCleaner` callback normalises these differences before they reach the provider. See `litellm_proxy/callbacks.py` for the cleaning rules.

- **Cost and token tracking**: The proxy logs input/output tokens per call with cached-token breakdown. This feeds operational dashboards without requiring agents to implement custom telemetry. The `GenerationEvent` entity records these metrics, but the proxy provides the source of truth.

- **Model routing flexibility**: The proxy can route `cohere/command-a-plus` to either Cohere Cloud or Azure-hosted endpoints by changing the config file. Agents remain unaware of the hosting topology.

## Alternatives Rejected
| Option | Why Rejected |
|---|---|
| Direct OpenAI/Anthropic/Cohere SDKs per agent | Duplicated retry logic, no unified observability, provider lock-in at the code level. |
| Build custom proxy service | Requires building message cleaning, rate limiting, retry, and logging that LiteLLM already provides battle-tested. Maintenance burden not justified. |
| Use provider SDKs with adapter layer | Still requires per-provider implementation of cleanup logic and retry; LiteLLM's OpenAI-compatible API is simpler than a custom adapter. |

## Tradeoffs
- **Pro**: Single point for LLM configuration, observability, and cleanup. Model switching requires only config changes.
- **Pro**: Provider-specific quirks (reasoning tokens, message format) handled once in the proxy, not duplicated across agents.
- **Con**: Additional infrastructure component to deploy and monitor. Requires Docker service (`litellm`) running alongside the application.
- **Con**: Latency: one additional network hop through the proxy. Mitigated by co-locating proxy in the same Docker network.

## Compliance

### Compliant
```python
# agents/first_message_agent.py
from openai import AsyncOpenAI
from app.config import settings

llm_client = AsyncOpenAI(
    base_url=settings.LITELLM_BASE_URL,  # http://litellm:4000/v1
    api_key=settings.LITELLM_API_KEY,
)

response = await llm_client.chat.completions.create(
    model="cohere/command-a-plus",  # logical name, proxy routes to Cohere
    messages=[...],
    max_tokens=1000,
)
```

### Non-Compliant
```python
# agents/first_message_agent.py — BYPASSES PROXY
import cohere  # Direct SDK import

client = cohere.AsyncClient(api_key=os.environ["COHERE_API_KEY"])

response = await client.chat(
    model="command-a-plus",  # Direct Cohere model name
    message=prompt,
)
```

## Cross-References
- [ADR-004: Transactional Outbox](./004-transactional-outbox-for-event-persistence.md) — LLM calls that produce events use the outbox pattern for generation events
- [Architecture: FirstMessageAgent](../03-agents/first-message-agent.md) — Agent contract assumes proxy-based LLM access
- [Architecture: GenerationEvent](../01-entities/generation-event.md) — Token metrics recorded by proxy are the authoritative source for GenerationEvent

## Implementation Notes
- **Proxy configuration location**: `litellm_proxy/pheidipp_litellm_config.yaml`
- **Custom callback logic**: `litellm_proxy/callbacks.py` (MessageHistoryCleaner)
- **Docker service**: Defined in root `docker-compose.yml` under `services.litellm`
- **Environment variables**: `LITELLM_API_KEY` (for proxy auth), `LITELLM_BASE_URL` (default: `http://litellm:4000/v1`)
- **Model naming convention**: Use `<provider>/<model-name>` format (e.g., `cohere/command-a-plus`, `openai/gpt-4`). The proxy strips the provider prefix when routing to the actual API.

## Failure Semantics
When the proxy is unavailable:
- OpenAI client raises `APIConnectionError` or `APITimeoutError`
- Agents should catch these, write a `GenerationEvent` with `success=false` and `failure_reason='proxy_unavailable'`, and return 503 to the caller
- The proxy's own error responses (4xx, 5xx) are propagated as OpenAI-compatible errors
