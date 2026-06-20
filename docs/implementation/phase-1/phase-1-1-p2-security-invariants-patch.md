# Implementation Plan: Phase-1.1-P2 — Security Invariants Patch
## Plan ID: Phase-1.1-P2

## Sub-Phase Reference
Sub-Phase ID: Phase-1.1
Sub-Phase Title: Phase 1 — Email/Password Authentication (Patch)

## Objective
Apply a targeted security patch to the Phase-1.1 auth implementation. This plan enforces two invariants that were missing or weakened in the original implementation plan: **(1)** `token_hash` is never returned by any API endpoint or included in any log, and **(2)** `ip_address` in `RefreshToken` records is truncated before logging and discarded from the database after 7 days. No other auth behaviour is changed.

## Scope
- **Invariant: `token_hash` non-disclosure.** Verify and harden all code paths (API responses, serializers, structured logs, event payloads) to guarantee the refresh-token hash is never leaked.
- **Invariant: `ip_address` truncation in logs/events.** Replace raw-IP emission with an IP-truncation utility that drops the last octet (/24 for IPv4) or last 64 bits (/64 for IPv6) before any log or event payload is written.
- **Invariant: `ip_address` discarded after 7 days.** Introduce an automated cleanup task that sets `ip_address = NULL` on `RefreshToken` records whose `created_at` is older than 7 days, while leaving the rest of the revocation record intact.
- **Testing.** Add concrete assertions and integration tests that prove the two invariants are upheld in production code paths.

## Out Of Scope
- OAuth, email verification, password reset, rate limiting, onboarding, or profile expansion.
- Changes to refresh-token rotation, JWT signing, bcrypt, or the `require_self` dependency.
- Modifying the 30-day refresh-token expiry or the append-only revocation-ledger semantics.
- Changes to the transactional outbox pattern or event publication mechanics other than the `ip_address` truncation.

 Wiriting this to:

## Architecture Contracts
- `01-entities/athlete-auth.md` — DEPENDS ON (invariant definitions for `token_hash` and `ip_address` handling)
- `docs/release-plan/phase-1/phase-1-1-email-password-auth.md` — DEPENDS ON (updated invariants)

## Invariants
- `token_hash` is never returned by any API endpoint or included in any log. Stored hashed for lookup without plaintext exposure.
- `ip_address` in `RefreshToken` records must be truncated to /24 (IPv4) or /64 (IPv6) before any logging or security analysis. For long-term storage, `ip_address` is extracted and discarded after 7 days via automated cleanup while the token record itself remains until 30-day expiration.
- All other invariants from the original Phase-1.1 plan remain in force.

## Implementation Steps
1. **Harden `token_hash` non-disclosure:**
   - Verify `RefreshToken` model is not included in any Pydantic response schema; if it is, remove `token_hash` from that schema.
   - Verify `logging_utils.ALLOWED_KEYS` does NOT contain `token_hash` or `refresh_token`. (It currently does not, but add a code comment referencing this invariant.)
   - Search the entire `app/` directory for any log call, `print`, or `repr` that might capture a `RefreshToken` instance directly. Replace with structured, allow-listed logging.
2. **Implement IP truncation utility:**
   - Create `app/utils/ip_utils.py` with a `truncate_ip(ip: str | None) -> str | None` function.
   - Implement `/24` for IPv4 and `/64` for IPv6. If the address is invalid or `None`, return `None`.
3. **Apply IP truncation to all log and event emission sites:**
   - In `auth_service.py`, update the `athlete_logged_in` event payload to use the truncated IP instead of the raw IP.
   - In `auth_service.py`, update any `_log` call that currently passes a raw `ip_address` to pass the truncated version.
   - Verify `_client_ip(request)` in the API layer returns the raw IP (for storage), and the truncation happens in the service layer before logging.
4. **Implement the 7-day IP discard mechanism:**
   - Add a new async function `RefreshTokenRepository.discard_old_ips()` that updates `ip_address = NULL` where `created_at < now - 7 days`.
   - Create a lightweight scheduled task (e.g., a Celery/ARQ task or a cron-driven script) that calls this repository method once daily. Given Phase-1.1 scope, this can be a simple recurring background task.
   - Ensure the task is idempotent and logs its actions safely (without the IPs it's discarding).
5. **Register the cleanup task:**
   - Add the new cleanup task to the project's scheduled task registry (e.g., `scripts/scheduled_tasks.py` or equivalent) to run daily at a quiet time (e.g., 03:00 UTC).
6. **Update documentation:**
   - Update `logging_utils.py` docstring to explicitly list `token_hash` and raw `ip_address` as forbidden fields.

## Pseudocode
```python
# New utility in app/utils/ip_utils.py
def truncate_ip(ip: str | None) -> str | None:
    if ip is None:
        return None
    try:
        if is_ipv4(ip):
            return ip.rsplit('.', 1)[0] + '.0/24'
        elif is_ipv6(ip):
            # Truncate to /64
            return ipaddress.IPv6Address(ip).exploded[:19] + '::/64'
    except ValueError:
        return None

# In AuthService.register / login / rotate_refresh_token
# Store raw IP in DB (for 7 days)
token = RefreshToken(..., ip_address=raw_ip)

# Emit event with truncated IP
await events.publish(..., payload={"ip_address": truncate_ip(raw_ip), ...})

# Daily cleanup task
async def discard_old_refresh_token_ips():
    await refresh_token_repo.discard_ips_older_than(days=7)
```

## Testing Requirements
- **`test_token_hash_not_in_api_response`**: Register a user, verify the response JSON does not contain the key `token_hash` anywhere in the payload structure.
- **`test_token_hash_not_in_logs`**: Register a user, capture `logging` output, assert no `token_hash` string is present in any log record.
- **`test_ip_is_truncated_in_system_events`**: Trigger a login. Fetch the corresponding `SystemEvent` from the DB. Assert the `ip_address` in the payload ends with '/24' or '/64'.
- **`test_ip_is_discarded_after_7_days`**: Manually create a `RefreshToken` record with a fake IP and a `created_at` of 8 days ago. Run the cleanup task. Assert the record's `ip_address` is now `NULL`.
- **`test_ip_is_preserved_for_6_days`**: Create a record with a fake IP and a `created_at` of 6 days ago. Run the cleanup task. Assert the `ip_address` is still present.
- **`test_truncate_ip_logic`**: Unit test for `truncate_ip` covering valid IPv4, valid IPv6, invalid strings, and `None`.

## Coder Handoff Notes
- **Do not** change the storage of the raw IP in the `RefreshToken` table on initial creation. The raw IP is intentionally stored for the 7-day window.
- The daily cleanup task is a new file; ensure it is wired into the project's task runner (Celery, APScheduler, etc.) or a startup script.
- If the project does not yet have a task runner, implement the cleanup as a standalone script that can be invoked by cron, as the primary goal is to satisfy the invariant.
- Ensure the `truncate_ip` utility handles IPv6 correctly. A simple string split might not be sufficient for all IPv6 formats; use the `ipaddress` standard library module.
- Keep user-facing errors and the brand philosophy unchanged; this is an internal security patch.
