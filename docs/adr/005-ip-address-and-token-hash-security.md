---
id: ADR-005
status: accepted
tags: [security, auth, privacy, gdpr]
supersedes: ~
superseded-by: ~
---

# ADR 005: IP Address and Token Hash Security Handling

## Rules
- **IP Logging Constraint** — `ip_address` must be truncated to /24 (IPv4) or /64 (IPv6) before any logging or security analysis.
- **IP Storage Retention** — `ip_address` extracted from `RefreshToken` records and discarded after 7 days via automated cleanup task; token record itself persists until 30-day expiration.
- **Token Hash Exclusion** — `token_hash` is never returned by any API endpoint or included in any log.

## Decision
Strengthen the `ip_address` invariant to require 7-day retention limit and mandatory anonymization before logging, and explicitly add `token_hash` to the set of fields excluded from API responses and logs.

## Rationale
- The invariant wording "if used for security analysis, it must be anonymized" was too narrow — it did not cover storage retention or routine log handling.
- Raw IP addresses in the database create GDPR/Data-Privacy risk when exported; a 7-day discard window significantly reduces this liability.
- `token_hash` was missing from the invariant set despite being a credential-equivalent field (enables token lookup and session correlation).
- Validation identified both gaps as inconsistencies between implementation and documented invariants.

## Alternatives Rejected

| Option | Why Rejected |
|---|---|
| Status quo (no change) | Leaves privacy risk unaddressed; invariant wording remains ambiguous for implementation. |
| Immediate hashing at storage | Requires migration of existing data; introduces implementation risk without retention cap. |
| No retention limit, only logging constraint | Retains long-term privacy liability if DB is ever accessed for security analysis. |
| Hash + 7-day retention | More complex key management; truncation provides sufficient anonymity for running-app scope. |

## Tradeoffs
- **Pro**: Reduces privacy liability without requiring key management or breaking existing token workflows.
- **Pro**: Explicit `token_hash` invariant prevents accidental exposure in future logging implementations.
- **Con**: Automated cleanup adds a scheduled task dependency for security compliance.
- **Con**: Truncation reduces forensic precision (e.g., cannot distinguish devices on same subnet).

## Compliance

**Compliant**
```python
# Auth service logs IP truncated to /24
log_event("athlete.logged_in", {
    "athlete_id": athlete_id,
    "ip_address": truncate_ip_to_cidr(ip_address, "/24"),  # IPv4 truncation
})

# Cleanup task extracts/discards IPs after 7 days
UPDATE athlete_refresh_tokens SET ip_address = NULL 
WHERE created_at < NOW() - INTERVAL '7 days'
```

**Non-compliant**
```python
# Logging raw IP — violates anonymization rule
log_event("athlete.logged_in", {
    "athlete_id": athlete_id,
    "ip_address": "192.168.1.42",  # never log full address
})

# No retention limit — violates cleanup rule
# Raw IP remains in DB beyond 7 days
```

## Cross-References
- [ADR-004: Transactional Outbox for Event Persistence](./004-transactional-outbox-for-event-persistence.md) — event logging pipeline uses same anonymization constraints.