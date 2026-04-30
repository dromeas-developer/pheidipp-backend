---
name: docker
description: Use when building Docker images, modifying docker-compose services, or working with container infrastructure for the pheidipp project
---

# Docker Standards — Pheidipp

## Service Map
| Service | Image | Port | Notes |
|---|---|---|---|
| api | python:3.11-slim (custom) | 8000 | FastAPI app |
| worker | same as api | — | ARQ job processor |
| db | timescale/timescaledb-ha:pg16-latest | 5432 | Must expose 5432 for local alembic |
| redis | redis:7-alpine | 6379 | ARQ broker |
| minio | minio/minio:latest | 9000/9001 | FIT file storage |
| opentopodata | ghcr.io/ajnisbet/opentopodata | 5100 | Elevation/GAP |
| tilecache | nginx:1.25-alpine | 8080 | OSM tile proxy |

## Multi-Stage Build (api + worker)
```dockerfile
# Stage 1 — builder: installs dependencies with build tools
FROM python:3.11 AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2 — final: lean runtime image
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY app/ app/
ENV PATH=/root/.local/bin:$PATH
```
- Target image size: < 300MB
- Never include build tools, caches, or dev dependencies in final image
- All containers MUST run as non-root

## Volumes
- Named volumes for all stateful services — never bind-mount database storage
- Bind mounts for app code in dev only
- db MUST expose port 5432 to host for Alembic to run outside Docker

## Networking
- Internal (container-to-container): use service names `db`, `redis`, `minio`
- External (host → container): use `localhost`
- Host resolution is handled automatically by `get_postgres_url()` in `app/core/config.py`
- Do NOT manually edit DATABASE_URL for environment — the function handles it

## Healthchecks (Required)
- All stateful services MUST define healthchecks
- API service MUST depend on `db`, `redis`, `minio` with `condition: service_healthy`
- Do NOT assume services are ready at startup

## Command Execution (STRICT)
NEVER run `docker` or `docker compose` directly.
ALWAYS use scripts:
- `bash scripts/docker-up.sh` — start services
- `bash scripts/docker-down.sh` — stop services  
- `bash scripts/docker-logs.sh` — view logs
- `bash scripts/db-upgrade.sh` — apply migrations (runs against exposed port 5432)
If a required script is missing → STOP and report.

## ARQ Worker Pattern
- Worker runs as a separate service using the same image as api
- Shares the same environment variables
- Does NOT expose ports
- Triggered via Redis — never called directly