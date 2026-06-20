"""FastAPI dependency wiring for Pheidipp."""

from app.api.deps import (
    build_auth_service,
    get_current_athlete_id,
    get_db,
    require_self,
)

__all__ = [
    "build_auth_service",
    "get_current_athlete_id",
    "get_db",
    "require_self",
]
