"""IP address utility — anonymisation before logging and event publication.

Implements the truncation rule from ADR-005
(``docs/adr/005-ip-address-and-token-hash-security.md``):

* IPv4 addresses are truncated to ``/24`` (retain the network octets,
  zero out the host octet).
* IPv6 addresses are truncated to ``/64`` (retain the network prefix).
* Invalid input or ``None`` returns ``None`` — the caller should drop the
  field rather than emit a raw address.

Raw IPs are NEVER passed to this module; only values that will be
written to a log line or an outbox event payload are truncated here.
The raw address is still permitted inside the ``RefreshToken`` table
where it is bound by the 7-day retention window enforced by the
discard task.
"""

from __future__ import annotations

import ipaddress
from typing import Optional

# Reduced-form prefixes per ADR-005. The constants are exported so tests
# can assert against the architectural contract without reproducing the
# literal strings.
IPV4_PREFIX_BITS = 24
IPV6_PREFIX_BITS = 64


def truncate_ip(ip: Optional[str]) -> Optional[str]:
    """Truncate ``ip`` to its ``/24`` (IPv4) or ``/64`` (IPv6) prefix.

    Returns a string in CIDR notation when the input is valid, ``None``
    otherwise. The CIDR suffix in the result is intentional — it makes
    truncation auditable in downstream log/event aggregates and is the
    canonical form mandated by ADR-005's compliance examples.
    """
    if ip is None or not isinstance(ip, str):  # type: ignore[unnecessary-isinstance] — runtime guard against non-str callers
        return None
    if not ip.strip():
        return None
    candidate = ip.strip()
    try:
        address = ipaddress.ip_address(candidate)
    except ValueError:
        return None

    if isinstance(address, ipaddress.IPv4Address):
        network = ipaddress.ip_network(f"0.0.0.0/{IPV4_PREFIX_BITS}", strict=False)
        truncated = ipaddress.IPv4Network(
            (int(address) & int(network.netmask)), strict=False
        )
        return f"{truncated.network_address.compressed}/{IPV4_PREFIX_BITS}"

    # IPv6
    v6_network = ipaddress.ip_network(f"::/{IPV6_PREFIX_BITS}", strict=False)
    masked_int = int(address) & int(v6_network.netmask)
    truncated_v6 = ipaddress.IPv6Address(masked_int)
    return f"{truncated_v6.compressed}/{IPV6_PREFIX_BITS}"
