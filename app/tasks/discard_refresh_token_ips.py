from __future__ import annotations

import logging
from typing import Optional

from app.db.session import AsyncSessionLocal
from app.repositories.refresh_token_repository import RefreshTokenRepository

logger = logging.getLogger("pheidipp.tasks.discard_refresh_token_ips")


async def discard_refresh_token_ips(
    *,
    retention_days: Optional[int] = None,
) -> int:
    async with AsyncSessionLocal() as session:
        repository = RefreshTokenRepository(session)
        discarded = await repository.discard_old_ips(retention_days=retention_days)
        await session.commit()
    logger.info(
        "refresh_token_ip_discard.completed",
        extra={
            "discarded_count": discarded,
            "retention_days": retention_days
            if retention_days is not None
            else RefreshTokenRepository.IP_RETENTION_DAYS,
        },
    )
    return discarded
