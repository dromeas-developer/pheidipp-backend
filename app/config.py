from pydantic import Field, AnyUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import urlparse


class Settings(BaseSettings):
    DATABASE_URL: str = Field(default="")
    APP_HOST: str = Field(default="0.0.0.0")
    APP_PORT: int = Field(default=8000, ge=1024, le=65535)
    DEBUG_MODE: bool = Field(default=False, validation_alias="DEBUG")
    APP_NAME: str = Field(default="pheidipp-backend")
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")
    LITELLM_API_KEY: str = Field(default="")
    LITELLM_BASE_URL: str = Field(default="http://litellm:4000/v1")
    LLM_MODEL: str = Field(default="cohere/command-a-plus")
    JWT_SECRET_KEY: str = Field(default="")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15)
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=30)
    JWT_ISSUER: str = Field(default="pheidipp-api")
    # Object storage — Phase-1.6. S3-compatible (AWS S3 / MinIO).
    S3_ENDPOINT_URL: str = Field(default="")
    S3_BUCKET: str = Field(default="pheidipp-fit-files")
    S3_REGION: str = Field(default="us-east-1")
    S3_ACCESS_KEY: str = Field(default="")
    S3_SECRET_KEY: str = Field(default="")
    S3_USE_SSL: bool = Field(default=False)
    # Heuristic HR constants — Phase-1.6.
    POPULATION_RESTING_HR_BPM: int = Field(default=60, ge=30, le=100)
    POPULATION_MAX_HR_FALLBACK_BPM: int = Field(default=190, ge=120, le=230)
    # Procrastinate task queue — Phase-1.7. PostgreSQL-backed worker queue.
    PROCRASTINATE_DATABASE_URL: str = Field(default="")

    model_config = SettingsConfigDict(env_file=".env", extra="allow")

settings = Settings()

def get_postgres_url(sync: bool = False) -> str:
    import socket
    url = settings.DATABASE_URL
    
    if sync:
        url = url.replace("postgresql+asyncpg", "postgresql+psycopg2")
    
    if "db" in url:
        try:
            s = socket.socket()
            s.settimeout(2)
            result = s.connect_ex(('db', 5432))
            s.close()
            if result == 0:
                return url
        except Exception:
            pass
        return url.replace("db", "localhost")

    return url


def get_procrastinate_dsn() -> str:
    """Return a libpq-format DSN for the procrastinate worker.

    ``procrastinate.contrib.psycopg2.Psycopg2Connector`` talks directly
    to psycopg2 — not SQLAlchemy — so it expects a libpq-format URL
    with no ``+driver`` suffix (see
    ``docs/implementation/phase-1/phase-1-8-p1-fix-event-ordering-and-async-processing.md``
    Step 0 for the rationale).

    The ``PROCRASTINATE_DATABASE_URL`` setting is provided in
    SQLAlchemy format (``postgresql+psycopg2://...``) for consistency
    with ``DATABASE_URL``; the SQLAlchemy ``+driver`` suffix is
    stripped here, in one place, so callers don't have to know
    about the conversion.

    This is deliberately a separate helper from
    :func:`get_postgres_url` for three reasons:

    * It operates on a different setting
      (``PROCRASTINATE_DATABASE_URL``) so the worker pool and the
      API pool can be configured independently.
    * It does not perform the dev-environment ``db`` -> ``localhost``
      hostname swap — the worker runs in its own container with its
      own DNS, so that probe is meaningless.
    * It is a *driver-prefix* concern, not a *connection-routing*
      concern, and mixing the two would overload a single helper.
    """
    return settings.PROCRASTINATE_DATABASE_URL.replace(
        "postgresql+psycopg2://", "postgresql://"
    )