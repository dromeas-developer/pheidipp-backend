---
name: stack-reference-sources
description: >
  Curated list of authoritative web sources for the Pheidipp stack
  (SQLAlchemy, FastAPI, Pydantic, Procrastinate, TimescaleDB, pgvector,
  pytest-asyncio, LiteLLM, MinIO, Alembic, Docker Compose, PostgreSQL)
  plus general-purpose sites (Stack Overflow, GitHub search, dev.to).
  Loaded by s-web-researcher to prioritize reliable sources over
  generic search results.
---

# Stack Reference Sources

Curated source list for web research on the Pheidipp stack. Use these
sources first — they are more reliable than generic search results.
For each library, the official docs and GitHub repo are the primary
authorities; the issue tracker is for known bugs and breaking changes.

---

## Pheidipp Stack Libraries

### SQLAlchemy 2.0 (async)

| Source | URL | Use For |
|---|---|---|
| Official docs | https://docs.sqlalchemy.org/en/20/ | API reference, async session patterns, query construction |
| GitHub repo | https://github.com/sqlalchemy/sqlalchemy | Source code, release notes |
| Issue tracker | https://github.com/sqlalchemy/sqlalchemy/issues | Known bugs, regression reports, async-specific issues |
| Migration guide (1.4→2.0) | https://docs.sqlalchemy.org/en/20/changelog/migration_20.html | Breaking changes from 1.x to 2.0 |

Search prefix: `site:docs.sqlalchemy.org/en/20/ <term>`

### FastAPI

| Source | URL | Use For |
|---|---|---|
| Official docs | https://fastapi.tiangolo.com/ | Route handlers, dependency injection, middleware, lifespan |
| GitHub repo | https://github.com/fastapi/fastapi | Source code, release notes |
| Issue tracker | https://github.com/fastapi/fastapi/issues | Known bugs, feature requests |
| Starlette docs | https://www.starlette.io/ | Underlying ASGI framework (middleware, responses, routing) |

Search prefix: `site:fastapi.tiangolo.com <term>`

### Pydantic v2

| Source | URL | Use For |
|---|---|---|
| Official docs | https://docs.pydantic.dev/latest/ | model_validate, model_dump, field validators, JSON schema |
| GitHub repo | https://github.com/pydantic/pydantic | Source code, release notes |
| Issue tracker | https://github.com/pydantic/pydantic/issues | Known bugs, v1→v2 migration issues |
| Migration guide (v1→v2) | https://docs.pydantic.dev/latest/migration/ | Breaking changes from v1 to v2 |

Search prefix: `site:docs.pydantic.dev <term>`

### Procrastinate (async job queue)

| Source | URL | Use For |
|---|---|---|
| Official docs | https://procrastinate.readthedocs.io/ | Job definition, defer, worker setup, PostgreSQL backend |
| GitHub repo | https://github.com/procrastinate-org/procrastinate | Source code, release notes |
| Issue tracker | https://github.com/procrastinate-org/procrastinate/issues | Known bugs, async-specific issues |

Search prefix: `site:procrastinate.readthedocs.io <term>`

### TimescaleDB

| Source | URL | Use For |
|---|---|---|
| Official docs | https://docs.timescale.com/ | Hypertable creation, continuous aggregates, compression |
| GitHub repo | https://github.com/timescale/timescaledb | Source code, release notes |
| Issue tracker | https://github.com/timescale/timescaledb/issues | Known bugs, performance issues |
| SQL API reference | https://docs.timescale.com/api/latest/ | create_hypertable, time_bucket, compression functions |

Search prefix: `site:docs.timescale.com <term>`

### pgvector

| Source | URL | Use For |
|---|---|---|
| GitHub repo | https://github.com/pgvector/pgvector | Installation, usage, index types (IVFFlat, HNSW) |
| README | https://github.com/pgvector/pgvector#readme | Quick reference, supported index types, distance functions |
| Issue tracker | https://github.com/pgvector/pgvector/issues | Known bugs, performance tuning, index build issues |

Search prefix: `site:github.com/pgvector/pgvector <term>`

### pytest-asyncio

| Source | URL | Use For |
|---|---|---|
| GitHub repo | https://github.com/pytest-dev/pytest-asyncio | Configuration, async fixtures, event loop scope |
| Issue tracker | https://github.com/pytest-dev/pytest-asyncio/issues | Known bugs, fixture scope issues, event loop conflicts |
| PyPI | https://pypi.org/project/pytest-asyncio/ | Version history, changelog |

Search prefix: `site:github.com/pytest-dev/pytest-asyncio <term>`

### LiteLLM (proxy + SDK)

| Source | URL | Use For |
|---|---|---|
| Official docs | https://docs.litellm.ai/ | Proxy setup, model routing, fallbacks, cost tracking |
| GitHub repo | https://github.com/BerriAI/litellm | Source code, release notes |
| Issue tracker | https://github.com/BerriAI/litellm/issues | Known bugs, provider-specific issues, proxy config |
| Proxy docs | https://docs.litellm.ai/docs/proxy/quick_start | Proxy server setup, config.yaml, router settings |

Search prefix: `site:docs.litellm.ai <term>`

### MinIO (S3-compatible storage)

| Source | URL | Use For |
|---|---|---|
| Official docs | https://min.io/docs/minio/linux/ | Server setup, bucket management, S3 API compatibility |
| GitHub repo | https://github.com/minio/minio | Source code, release notes |
| Python SDK docs | https://min.io/docs/minio/linux/developers/python/ | minio-py client, presigned URLs, multipart uploads |
| Issue tracker | https://github.com/minio/minio/issues | Known bugs, S3 API edge cases |

Search prefix: `site:min.io/docs/minio <term>`

### Alembic

| Source | URL | Use For |
|---|---|---|
| Official docs | https://alembic.sqlalchemy.org/en/latest/ | Migration generation, upgrade/downgrade, branching |
| GitHub repo | https://github.com/sqlalchemy/alembic | Source code, release notes |
| Issue tracker | https://github.com/sqlalchemy/alembic/issues | Known bugs, autogenerate issues, async migration issues |
| Cookbook | https://alembic.sqlalchemy.org/en/latest/cookbook.html | Common patterns: adding columns, data migrations, enums |

Search prefix: `site:alembic.sqlalchemy.org <term>`

### Docker Compose

| Source | URL | Use For |
|---|---|---|
| Official docs | https://docs.docker.com/compose/ | Service definitions, networking, volumes, healthchecks |
| GitHub repo | https://github.com/docker/compose | Source code, release notes |
| Issue tracker | https://github.com/docker/compose/issues | Known bugs, compose-spec issues |
| Compose spec | https://compose-spec.github.io/compose-spec/ | Canonical spec for docker-compose.yml fields |

Search prefix: `site:docs.docker.com/compose <term>`

### PostgreSQL

| Source | URL | Use For |
|---|---|---|
| Official docs | https://www.postgresql.org/docs/ | SQL reference, configuration, extensions |
| GitHub repo (mirror) | https://github.com/postgres/postgres | Source code |
| Issue tracker | https://www.postgresql.org/list/pgsql-bugs/ | Bug reports |
| Wiki | https://wiki.postgresql.org/ | Performance tuning, admin guides |

Search prefix: `site:postgresql.org/docs <term>`

---

## General-Purpose Sources

Use these when the topic doesn't match a specific library above, or
when you need community discussion / workarounds.

| Source | URL | Use For |
|---|---|---|
| Stack Overflow | https://stackoverflow.com/ | Error messages, common pitfalls, community solutions |
| GitHub search | https://github.com/search | Code examples, issue discussions across repos |
| GitHub code search | https://github.com/search?type=code | Find usage patterns in real codebases |
| dev.to | https://dev.to/ | Tutorials, deep dives, practical guides |
| Real Python | https://realpython.com/ | Python-specific tutorials, best practices |
| PyPI | https://pypi.org/ | Package versions, changelogs, dependency info |
| Reddit r/Python | https://www.reddit.com/r/Python/ | Community discussion, library comparisons |

Search prefixes:
- `site:stackoverflow.com <error message>`
- `site:github.com <library> <term>`
- `site:dev.to <library> <term>`

---

## Search Strategy

1. **Identify the library** from the research topic. If it matches a
   stack library above, search its official docs and issue tracker
   first.
2. **Use site-restricted queries** for authoritative domains. Example:
   `site:docs.sqlalchemy.org/en/20/ async session merge`
3. **Fall back to general sources** (Stack Overflow, GitHub search) if
   the official docs don't answer the question.
4. **Check version compatibility** — prefer results matching the
   version range in the research context. SQLAlchemy 2.0 answers
   don't apply to 1.x code; Pydantic v2 answers don't apply to v1.
5. **Prefer recent results** — within the last 2 years unless the
   topic is about a stable, unchanged API.
