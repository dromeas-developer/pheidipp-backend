"""Unit tests for safe audit logging (ADR-005 logging invariants).

These tests assert the contract that no credential, secret, or PII
field ever reaches a log handler — even if a careless caller hands the
logger a payload that contains them. The allow-list
(``ALLOWED_KEYS``) plus the deny-list (``FORBIDDEN_KEYS``) compose as
defence-in-depth.
"""

from __future__ import annotations

import logging

import pytest

from app.core import logging_utils


class TestSafeExtraFiltering:
    """``safe_extra`` strips forbidden keys and unknown keys."""

    def test_keep_only_allowed_keys(self) -> None:
        payload = {"athlete_id": "abc", "secret": "leak"}
        result = logging_utils.safe_extra(payload)
        assert result == {"athlete_id": "abc"}

    def test_strip_forbidden_keys(self) -> None:
        """Even allowed-key collisions with forbidden keys are stripped."""
        forbidden = {
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
        for key in forbidden:
            # None of these should survive safe_extra, even if passed
            # alongside an allowed key.
            payload = {"athlete_id": "abc", key: "secret-value"}
            assert key not in logging_utils.safe_extra(payload)

    def test_empty_payload_returns_empty_dict(self) -> None:
        assert logging_utils.safe_extra(None) == {}
        assert logging_utils.safe_extra({}) == {}


class TestAllowedKeysContract:
    """Snapshot tests against the documented ALLOWED/FORBIDDEN sets."""

    def test_allowed_keys_does_not_include_secrets(self) -> None:
        forbidden_in_allow = {
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
        assert forbidden_in_allow.isdisjoint(logging_utils.ALLOWED_KEYS)

    def test_forbidden_keys_is_superset_of_secrets(self) -> None:
        """Sanity: the deny-list must include every documented secret."""
        assert "hashed_password" in logging_utils.FORBIDDEN_KEYS
        assert "password" in logging_utils.FORBIDDEN_KEYS
        assert "token" in logging_utils.FORBIDDEN_KEYS
        assert "refresh_token" in logging_utils.FORBIDDEN_KEYS
        assert "token_hash" in logging_utils.FORBIDDEN_KEYS
        assert "provider_tokens" in logging_utils.FORBIDDEN_KEYS
        assert "provider_user_id" in logging_utils.FORBIDDEN_KEYS
        assert "ip_address" in logging_utils.FORBIDDEN_KEYS
        assert "email" in logging_utils.FORBIDDEN_KEYS


class TestLogEventEndToEnd:
    """End-to-end: ``log_event`` never leaks forbidden fields."""

    def test_log_event_strips_forbidden_fields(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.INFO, logger="pheidipp.auth")
        logging_utils.log_event(
            "athlete.login",
            athlete_id="abc",
            email="athlete@example.com",
            password="plaintext!",
            token_hash="abcd",
        )
        records = caplog.records
        assert records, "Expected at least one LogRecord"
        record = records[-1]
        # Verify the record's attrs never contain forbidden keys.
        for forbidden_key in logging_utils.FORBIDDEN_KEYS:
            assert not hasattr(record, forbidden_key), (
                f"LogRecord unexpectedly carries the forbidden key {forbidden_key!r}"
            )


class TestRecordMetric:
    """Metric recording respects the metric key registry."""

    def test_known_metric_is_recorded(self) -> None:
        before = logging_utils.snapshot_metrics()
        logging_utils.record_metric(
            "athlete.auth.logins.total",
            auth_provider="email",
            outcome="success",
        )
        after = logging_utils.snapshot_metrics()
        # Locate the counter we just incremented.
        entry = after["athlete.auth.logins.total"]["email|success"]
        previous = before.get("athlete.auth.logins.total", {}).get(
            "email|success", 0
        )
        assert entry == previous + 1

    def test_unknown_metric_is_silently_ignored(self) -> None:
        logging_utils.snapshot_metrics()
        logging_utils.record_metric("not.a.real.metric", auth_provider="email")
        after = logging_utils.snapshot_metrics()
        # No key should have been added.
        assert "not.a.real.metric" not in after


class TestSnapshotMetricsIsolation:
    """Snapshot returns a defensive copy so callers can't mutate state."""

    def test_snapshot_is_defensive_copy(self) -> None:
        before = logging_utils.snapshot_metrics()
        before["some.test.metric"] = {"x": 1}
        # Mutating the returned dict must not leak into the live store.
        # (We assign into ``before`` after the snapshot call — the
        # subsequent snapshot should still lack the synthetic key.)
        next_snap = logging_utils.snapshot_metrics()
        assert before is not next_snap
        assert "some.test.metric" not in next_snap
        # Restore: revert our manual mutation.
        before.pop("some.test.metric", None)
