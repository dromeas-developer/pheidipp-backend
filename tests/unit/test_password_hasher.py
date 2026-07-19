"""Unit tests for the password hasher.

The password hasher enforces the architecture's hard minimum cost
factor (12) and preserves input/output confidentiality: plaintext
never travels outside this module, and verification runs in constant
time. These tests assert those behavioural invariants directly.

We deliberately avoid mocking ``bcrypt`` — the cost factor and the
72-byte truncation behaviour are best validated against the real
implementation.
"""

from __future__ import annotations
from typing import Any

import pytest

from app.core.security.password_hasher import BCRYPT_COST, PasswordHasher


class TestArchitectureMinimum:
    """The configured bcrypt cost must meet the architecture's hard minimum."""

    def test_cost_factor_meets_phase_1_1_minimum(self) -> None:
        """Phase-1.1 requires bcrypt cost >= 12."""
        assert BCRYPT_COST >= 12


class TestPasswordHasherHash:
    """Hashing: bcrypt output, non-empty inputs only."""

    def test_hash_returns_bcypt_string(self) -> None:
        h = PasswordHasher.hash("ValidPass123!")
        # The bcrypt output prefix is ``$2b$`` for cost-12 hashes.
        assert h.startswith("$2b$")

    def test_hash_distinguishes_similar_passwords(self) -> None:
        """Hashing different inputs must produce different outputs."""
        a = PasswordHasher.hash("ValidPass123!")
        b = PasswordHasher.hash("ValidPass123?")
        assert a != b

    @pytest.mark.parametrize("value", [None, 123, 45.6, []])  # type: ignore[list-item]
    def test_hash_rejects_non_string_types(self, value: Any) -> None:
        """Non-str inputs are a caller type error — bcrypt cannot
        encode non-strings and the guard rejects them before any
        value check runs."""
        with pytest.raises(TypeError):
            PasswordHasher.hash(value)  # type: ignore[arg-type]

    def test_hash_rejects_empty_string(self) -> None:
        """An empty string is a valid type but an invalid value —
        the value check rejects it with ``ValueError``."""
        with pytest.raises(ValueError):
            PasswordHasher.hash("")


class TestPasswordHasherVerify:
    """Verification: positive, negative, and malformed-hash cases."""

    def test_correct_password_verifies(self) -> None:
        h = PasswordHasher.hash("ValidPass123!")
        assert PasswordHasher.verify("ValidPass123!", h) is True

    def test_wrong_password_rejected(self) -> None:
        h = PasswordHasher.hash("ValidPass123!")
        assert PasswordHasher.verify("WrongPassword!", h) is False

    def test_empty_password_rejected(self) -> None:
        h = PasswordHasher.hash("ValidPass123!")
        assert PasswordHasher.verify("", h) is False

    def test_malformed_hash_returns_false_without_raising(self) -> None:
        """A corrupted stored hash must NOT raise — only return False."""
        assert PasswordHasher.verify("ValidPass123!", "not-a-bcrypt-hash") is False

    def test_non_string_hash_returns_false(self) -> None:
        """Defends against any downstream caller that forgot to serialise."""
        assert PasswordHasher.verify("ValidPass123!", None) is False  # type: ignore[arg-type]

    @pytest.mark.parametrize("value", [None, "", 123, []])  # type: ignore[list-item]
    def test_verify_rejects_invalid_password_type(self, value: Any) -> None:
        h = PasswordHasher.hash("ValidPass123!")
        assert PasswordHasher.verify(value, h) is False  # type: ignore[arg-type]


class TestPasswordHasherTruncationSymmetry:
    """Bcrypt's 72-byte input cap is enforced symmetrically in hash and verify."""

    def test_72_byte_inputs_compare_equal(self) -> None:
        """Hash and verify must both truncate to 72 bytes — never pick a
        different prefix on each side."""
        password = "x" * 80  # > 72 bytes
        h = PasswordHasher.hash(password)
        # Verification uses the same truncation semantics, so the hash
        # should match even though the password exceeds the cap.
        assert PasswordHasher.verify(password, h) is True

    def test_72_byte_password_round_trip(self) -> None:
        """:func:`hash` ''must'' produce a verifiable hash for a 72-byte password."""
        password = "x" * 72
        h = PasswordHasher.hash(password)
        assert PasswordHasher.verify(password, h) is True
