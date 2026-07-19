# app/utils/

## Purpose
Shared utility functions with no database or service-layer dependencies. These are pure helpers callable from any layer — they accept plain values, return plain values, and never touch `AsyncSession` or configuration state.

## Contents
### Shared Helpers
| File | Responsibility |
|---|---|
| `email_utils.py` | `normalize_email` — lowercase + strip for case-insensitive email matching before persistence or lookup |
| `ip_utils.py` | `truncate_ip` — anonymise IP addresses to `/24` (IPv4) or `/64` (IPv6) CIDR prefixes per ADR-005 before logging or event publication |

## Architecture Notes
- `normalize_email` is the single canonical email-normalization point — all layers must call it before persistence or lookup to ensure consistency with the database's `lower(email)` unique index.
- `truncate_ip` is called only on values destined for logs or event payloads — raw IPs are permitted inside `RefreshToken` rows where the 7-day retention window applies.
- Both functions are pure (no side effects, no I/O) and safe to call synchronously from any context.
