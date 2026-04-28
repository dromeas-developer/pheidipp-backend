# Pheidipp

[`README.md`](README.md)

## 🏃‍♂️ High-Level Summary

Pheidipp is an **agentic running application** designed to ingest, process, and analyze running activity data (e.g., FIT files) using a layered, async-first architecture. The system integrates:

- **FastAPI** for the backend API
- **PostgreSQL with TimescaleDB and pgvector** for structured, time-series, and vector data
- **Redis + ARQ** for background job processing
- **MinIO** for object storage of raw activity files
- **LangGraph** for agent orchestration and memory agents

The platform provides real-time and historical analytics, elevation-aware metrics, and AI-driven insights for runners.

---

## 🎯 Project Objective

Pheidipp aims to:

1. **Ingest** raw running activity data (FIT files) from various sources (e.g., Garmin, COROS).
2. **Process** and enrich data with elevation, grade-adjusted pace (GAP), and other derived metrics.
3. **Store** structured, time-series, and vectorized data efficiently.
4. **Analyze** running performance using both traditional analytics and AI-driven agents.
5. **Provide** a scalable, async-first backend that supports real-time dashboards and background processing.

The system is built for **local-first development** and **cloud-ready deployment**, with a focus on **separation of concerns**, **async I/O**, and **scalable data pipelines**.

---

## 🏗️ Target Project Structure

```
/home/ruimendes/projects/pheidipp/backend
├── [`app/`](app/)
│   ├── [`agents/`](app/agents/)
│   │   └── LangGraph DAGs and agent orchestration logic
│   ├── [`api/`](app/api/)
│   │   ├── [`routes/`](app/api/routes/)
│   │   │   ├── [`athletes.py`](app/api/routes/athletes.py)
│   │   │   └── [`health.py`](app/api/routes/health.py)
│   │   └── FastAPI route handlers and endpoint definitions
│   ├── [`db/`](app/db/)
│   │   ├── [`session.py`](app/db/session.py)
│   │   └── Async SQLAlchemy session management
│   ├── [`models/`](app/models/)
│   │   └── SQLAlchemy ORM models (source of truth for schema)
│   ├── [`repositories/`](app/repositories/)
│   │   └── Data access layer using Async SQLAlchemy
│   ├── [`schemas/`](app/schemas/)
│   │   └── Pydantic v2 models for request/response validation
│   ├── [`services/`](app/services/)
│   │   └── Core business logic and orchestration
│   └── [`worker/`](app/worker/)
│       └── ARQ background job definitions
├── [`alembic/`](alembic/)
│   └── Database migration scripts (Alembic)
├── [`tests/`](tests/)
│   └── Test suite
├── [`docker-compose.yml`](docker-compose.yml)
├── [`Dockerfile`](Dockerfile)
├── [`requirements.txt`](requirements.txt)
└── [`README.md`](README.md)
```

---

## 🏛️ Architecture Constraints & Design Principles

### ⚡ Core Runtime & Stack
- **Language**: Python 3.11+
- **Framework**: FastAPI (async-first)
- **ORM**: SQLAlchemy 2.0 (async)
- **Validation**: Pydantic v2
- **Background Jobs**: ARQ + Redis
- **Database**: PostgreSQL with TimescaleDB (time-series) and pgvector (vector search)
- **Object Storage**: MinIO (S3-compatible)
- **LLM Integration**: LangChain + centralized LLM routing (Groq, Cerebras, Mistral, OpenRouter)

### 🔄 Layered Architecture & Dependency Rules

| Layer | Responsibility | Depends On |
|-------|----------------|------------|
| [`api/`](app/api/) | Request/response handling | [`services/`](app/services/)
| [`services/`](app/services/) | Business logic & orchestration | [`repositories/`](app/repositories/), [`agents/`](app/agents/)
| [`repositories/`](app/repositories/) | Data access (Async SQLAlchemy) | [`models/`](app/models/)
| [`models/`](app/models/) | Database schema (SQLAlchemy ORM) | —
| [`schemas/`](app/schemas/) | Request/response validation (Pydantic) | —
| [`agents/`](app/agents/) | Agent orchestration (LangGraph) | [`services/`](app/services/)
| [`worker/`](app/worker/) | Background job processing (ARQ) | [`services/`](app/services/)

**Prohibited Dependencies**:
- [`api/`](app/api/) → [`repositories/`](app/repositories/) or [`models/`](app/models/)
- [`services/`](app/services/) → [`api/`](app/api/)
- [`agents/`](app/agents/) → [`repositories/`](app/repositories/) or [`models/`](app/models/)
- [`repositories/`](app/repositories/) → [`services/`](app/services/)

### 🗄️ Database & Schema
- **Source of Truth**: SQLAlchemy ORM models ([`app/models/`](app/models/))
- **Migrations**: Alembic (synchronous engine for migrations, async for application)
- **TimescaleDB Hypertables**:
  - `activity_samples` (time column: `timestamp`)
  - `fitness_metrics` (time column: `metric_date`)
- **Vector Search**: `activity_embeddings` table with `vector(384)` for cosine similarity (`<=>`)

### 🧩 Async & Non-Blocking Principles
- All database operations use `AsyncSession` and `async/await`.
- Blocking operations (e.g., FIT file parsing) are offloaded using `asyncio.to_thread()`.
- All background jobs are `async def` and non-blocking.
- **Never perform blocking I/O in async routes or jobs.**

### 🤖 Agent & LLM Integration
- **Agent Framework**: LangGraph
- **LLM Providers**: Groq, Cerebras, Mistral, OpenRouter (via centralized routing)
- **Memory Agents**: Triggered after activity ingestion for insights and digital twin updates.

### 📦 Object Storage & Processing
- **MinIO Bucket**: `pheidipp-fit-files` for raw FIT files
- **FIT Processing**: CPU-bound parsing executed via `asyncio.to_thread()`

### 🔧 Configuration
- All configuration is environment-driven (`.env` file + `pydantic_settings.BaseSettings`).
- No hardcoded credentials or environment-specific values.

---

## 🚀 Setup Instructions

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- PostgreSQL (with TimescaleDB and pgvector extensions)
- Redis
- MinIO (or S3-compatible storage)

### Local Development

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd /home/ruimendes/projects/pheidipp/backend
   ```

2. **Set up environment variables**:
   ```bash
   cp .env.example .env  # Update with your values
   ```

3. **Install dependencies**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Start infrastructure**:
   ```bash
   docker-compose up -d db redis minio
   ```

5. **Run database migrations**:
   ```bash
   alembic upgrade head
   ```

6. **Start the API**:
   ```bash
   uvicorn app.main:app --reload
   ```

7. **Start the worker** (in a separate terminal):
   ```bash
   arq app.worker.WorkerSettings
   ```

---

## 🌐 API Overview

The API is built with FastAPI and follows RESTful conventions. All endpoints are `async` and support:

- **Request/response validation** via Pydantic v2
- **Async database access** via SQLAlchemy 2.0
- **Background job triggering** via ARQ

### Example Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| [`/health/live`](app/api/routes/health.py:12) | GET | Liveness probe |
| [`/health/ready`](app/api/routes/health.py:19) | GET | Readiness probe (checks DB connectivity) |
| [`/athletes/`](app/api/routes/athletes.py:10) | POST | Create a new athlete |
| [`/athletes/`](app/api/routes/athletes.py:17) | GET | List all athletes |
| [`/athletes/{athlete_id}`](app/api/routes/athletes.py:23) | GET | Get athlete by ID |

---

## 🧪 Testing

Run the test suite with:

```bash
pytest tests/
```

---

## 📚 Further Reading

- [`pheidipp-stack-project-truth`](.roo/skills/pheidipp-stack-project-truth/SKILL.md): Core technical stack and architectural constraints.
- [`pheidipp-infrastructure`](.roo/skills/pheidipp-infrastructure/SKILL.md): High-level system map of services and responsibilities.
- [`pheidipp-docker-workflow`](.roo/skills/pheidipp-docker-workflow/SKILL.md): Docker and container orchestration standards.
- [`pheidipp-alembic-workflow`](.roo/skills/pheidipp-alembic-workflow/SKILL.md): Alembic migration procedures.