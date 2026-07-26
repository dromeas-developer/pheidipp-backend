from typing import cast

from app.utils.ip_utils import truncate_ip


class TestTruncateIp:
    def test_truncate_ipv4_to_24(self):
        result = truncate_ip("192.168.1.100")
        assert result == "192.168.1.0/24"

    def test_truncate_ipv6_to_64(self):
        result = truncate_ip("2001:db8:abcd:12ef::1")
        assert result == "2001:db8:abcd:12ef::/64"

    def test_truncate_ip_none_returns_none(self):
        assert truncate_ip(None) is None

    def test_truncate_ip_empty_string_returns_none(self):
        assert truncate_ip("") is None

    def test_truncate_ip_whitespace_string_returns_none(self):
        assert truncate_ip("   ") is None

    def test_truncate_ip_unparseable_string_returns_none(self):
        assert truncate_ip("not-an-ip-address") is None

    def test_truncate_ip_non_string_type_returns_none(self):
        assert truncate_ip(cast(str | None, 12345)) is None
