from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic.networks import PostgresDsn


class Settings(BaseSettings):
    POSTGRES_DSN: PostgresDsn = Field(..., validation_alias="DATABASE_URL")
    APP_HOST: str = Field(default="0.0.0.0", env="APP_HOST")
    APP_PORT: int = Field(default=8000, ge=1024, le=65535, env="APP_PORT")
    DEBUG_MODE: bool = Field(default=False, env="DEBUG")
    APP_NAME: str = Field(default="pheidipp-backend", env="APP_NAME")
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    REDIS_URL: str = Field(default="redis://redis:6379/0", env="REDIS_URL")
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


settings = Settings()