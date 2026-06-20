"""Unit tests for the IP truncation utility (P2 invariant).

Validates the ADR-005 contract:

* IPv4 inputs are reduced to their /24 network prefix in CIDR
  notation.
* IPv6 inputs are reduced to their /64 network prefix in CIDR
  notation.
* Invalid inputs and ``None`` return ``None`` rather than raising.

These tests are pure-function assertions — no DB or HTTP, so they run
fast and pinpoint regressions in the util module.
"""

from __future__ import annotations

import pytest

from app.utils.ip_utils import (
    IPV4_PREFIX_BITS,
    IPV6_PREFIX_BITS,
    truncate_ip,
)


class TestTruncateIpv4:
    """IPv4 truncation: /24 network retention, host octet zeroed."""

    def test_zeroes_host_octet(self) -> None:
        result = truncate_ip("192.168.1.42")
        assert result == "192.168.1.0/24"

    def test_strips_leading_zeros(self) -> None:
        """``10.0.0.1`` becomes ``10.0.0.0/24`` (no padded octets)."""
        result = truncate_ip("10.0.0.1")
        assert result == "10.0.0.0/24"

    def test_preserves_class_a_through_c(self) -> None:
        assert truncate_ip("8.8.8.8") == "8.8.8.0/24"
        assert truncate_ip("172.16.55.99") == "172.16.55.0/24"

    def test_strips_whitespace(self) -> None:
        # request.client.host may include accidental whitespace in tests.
        assert truncate_ip("  192.168.1.7  ") == "192.168.1.0/24"


class TestTruncateIpv6:
    """IPv6 truncation: /64 network prefix, all host bits zeroed."""

    def test_truncates_to_slash_sixty_four(self) -> None:
        result = truncate_ip("2001:db8:85a3::8a2e:370:7334")
        assert result is not None
        assert result.endswith(f"/{IPV6_PREFIX_BITS}")

    def test_drops_interface_id(self) -> None:
        """The last 64 bits (interface identifier) must be zero."""
        result = truncate_ip("2001:db8:85a3:0:0:8a2e:370:7334")
        assert result == "2001:db8:85a3::/64"

    def test_zero_address(self) -> None:
        """``::`` collapses to its own /64."""
        assert truncate_ip("::") == "::/64"


class TestTruncateInvalidInput:
    """Invalid input is normalised to ``None`` rather than raising."""

    @pytest.mark.parametrize(
        "value",
        [
            None,
            "",
            "   ",
            "not-an-ip",
            "999.999.999.999",
            "2001:db8:not::valid",
            12345,  # type: ignore[list-item]
        ],
    )
    def test_invalid_returns_none(self, value) -> None:
        assert truncate_ip(value) is None


class TestTruncatePrefixBitsExported:
    """Sanity check that the prefix constants match the ADR-005 contract."""

    def test_ipv4_prefix_is_24(self) -> None:
        assert IPV4_PREFIX_BITS == 24

    def test_ipv6_prefix_is_64(self) -> None:
        assert IPV6_PREFIX_BITS == 64
