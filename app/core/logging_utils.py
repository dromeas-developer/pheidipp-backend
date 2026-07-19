"""Safe audit logging for authentication events."""

from __future__ import annotations

import logging
import threading
from collections import Counter as CollectionsCounter
from typing import Any, Mapping

# Cardinal log fields for security monitoring. Anything outside these
# keys is silently dropped to prevent secret leakage via structured
# payloads.
#
# INVARIANT (ADR-005): ``token_hash``, ``refresh_token`` plaintext,
# ``hashed_password``, ``provider_tokens``, ``provider_user_id``,
# raw ``ip_address``, and ``email`` are NEVER included here. Adding
# any of them is a security regression.
ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        "athlete_id",
        "auth_provider",
        "event",
        "outcome",
        "token_type",
        "correlation_id",
    }
)

# Explicit denylist for credentials, secrets, and PII that MUST be
# dropped before any log line is constructed. ``safe_extra`` removes
# these keys as a defence-in-depth layer on top of the ``ALLOWED_KEYS``
# allow-list — the two filters compose so that even if a future change
# accidentally widens ``ALLOWED_KEYS``, sensitive fields stay
# suppressed. Mirror of the invariant declared in this module's
# docstring and in ``docs/adr/005-ip-address-and-token-hash-security.md``.
FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {
        "hashed_password",
        "password",
        "token",
        "refresh_token",
        "token_hash",
        "provider_tokens",
        "provider_user_id",
        "ip_address",
        "email",
    }
)

# Metric naming follows the architecture's observable spec
# (athlete.auth.registrations.total, athlete.auth.logins.total, etc.).
METRIC_KEYS: frozenset[str] = frozenset(
    {
        "athlete.auth.registrations.total",
        "athlete.auth.logins.total",
        "athlete.auth.logins.failed.total",
        "athlete.auth.refresh.total",
        "athlete.auth.refresh.failed.total",
        "athlete.auth.rotation.total",
    }
)

_metrics_lock = threading.Lock()
_metrics: dict[str, CollectionsCounter[str]] = {}

def safe_extra(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return only the allow-listed keys from *payload*."""
    if not payload:
        return {}
    return {
        k: v
        for k, v in payload.items()
        if k in ALLOWED_KEYS and k not in FORBIDDEN_KEYS
    }

def get_auth_logger() -> logging.Logger:
    """Return the namespaced logger used by the auth surface."""
    return logging.getLogger("pheidipp.auth")

def record_metric(
    name: str,
    *,
    auth_provider: str | None = None,
    outcome: str | None = None,
) -> None:
    """Increment an in-process metric counter with a (provider, outcome) label."""
    if name not in METRIC_KEYS:
        return
    label = f"{auth_provider or '-'}|{outcome or '-'}"
    with _metrics_lock:
        bucket = _metrics.setdefault(name, CollectionsCounter())
        bucket[label] += 1

def snapshot_metrics() -> dict[str, dict[str, int]]:
    """Return a copy of the current metric counters (debug / tests only)."""
    with _metrics_lock:
        return {name: dict(bucket) for name, bucket in _metrics.items()}

def log_event(event: str, **fields: Any) -> None:
    """Emit a structured log line with allow-listed fields only."""
    payload = safe_extra({"event": event, **fields})
    get_auth_logger().info(event, extra=payload)
