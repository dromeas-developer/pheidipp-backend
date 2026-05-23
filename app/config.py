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
    REDIS_URL: str = Field(default="redis://redis:6379/0")
    LOG_LEVEL: str = Field(default="INFO")
    LITELLM_API_KEY: str = Field(default="")
    LITELLM_BASE_URL: str = Field(default="http://litellm:4000/v1")
    LLM_MODEL: str = Field(default="cohere/command-a-plus")
    JWT_SECRET_KEY: str = Field(default="")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15)
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=30)
    JWT_ISSUER: str = Field(default="pheidipp-api")

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