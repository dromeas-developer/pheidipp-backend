"""Discard stale ``RefreshToken.ip_address`` values per ADR-005.

The transactional outbox path keeps the raw IP in
``athlete_refresh_tokens.ip_address`` for a 7-day retention window so
that short-lived session analysis can still correlate activity. This
task NULLs out the column on rows older than the window — the rest of
the revocation ledger (token hash, expiry, replacement linkage) is
preserved so its append-only semantics hold.

Intended execution modes:

* one-shot invocation by cron via ``scripts/discard-refresh-token-ips.sh``
* in-process invocation by an orchestrator (``await asyncio.gather(...)``)

The task is idempotent: re-running it is a no-op once all stale IPs
have been cleared. Failures are surfaced via standard exception
propagation so the caller can decide whether to retry or alert.
"""

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
    """Run the discard task once and return the affected row count.

    The countdown is in-process transactional and committed before the
    function returns. The caller (cron wrapper / test) decides whether
    a non-zero rowcount is success or an alert condition; this function
    does not log the row contents because doing so would require
    reading IPs that have just been redacted from the database.
    """
    async with AsyncSessionLocal() as session:
        repository = RefreshTokenRepository(session)
        discarded = await repository.discard_old_ips(
            retention_days=retention_days
        )
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
