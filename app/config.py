from pydantic import Field, AnyUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import urlparse


class Settings(BaseSettings):
    DATABASE_URL: str = Field(..., alias="DATABASE_URL")
    APP_HOST: str = Field(default="0.0.0.0", env="APP_HOST")
    APP_PORT: int = Field(default=8000, ge=1024, le=65535, env="APP_PORT")
    DEBUG_MODE: bool = Field(default=False, env="DEBUG")
    APP_NAME: str = Field(default="pheidipp-backend", env="APP_NAME")
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    REDIS_URL: str = Field(default="redis://redis:6379/0", env="REDIS_URL")
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LITELLM_API_KEY: str = Field(default="", env="LITELLM_API_KEY")
    LITELLM_BASE_URL: str = Field(default="http://litellm:4000/v1", env="LITELLM_BASE_URL")
    LLM_MODEL: str = Field(default="cohere/command-a-plus", env="LLM_MODEL")

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