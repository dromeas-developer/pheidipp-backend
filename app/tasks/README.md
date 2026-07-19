# app/tasks/

## Purpose
Standalone maintenance tasks intended for cron-job or orchestrator invocation. Each task manages its own `AsyncSession` lifecycle, commits independently, and is idempotent. Tasks are not part of the request/response cycle — they run out-of-band via shell scripts or async orchestrators.

## Contents
### Refresh Token
| File | Responsibility |
|---|---|
| `discard_refresh_token_ips.py` | `discard_refresh_token_ips` — NULLs out `RefreshToken.ip_address` on rows older than the 7-day retention window per ADR-005 |
| `discard_refresh_token_ips_cli.py` | CLI entry point for cron — parses `--retention-days`, runs the async task, exits 0 on success or 1 on failure |

## Architecture Notes
- Tasks create their own `AsyncSession` via `AsyncSessionLocal()` and own their commit boundary — they are independent of the FastAPI request lifecycle.
- Both task files are idempotent: re-running after all stale IPs are cleared is a no-op.
- The CLI module exposes a `main(argv)` entry point for `scripts/discard-refresh-token-ips.sh`; exit code 1 is the cron failure contract.

## Cross-References
- [ADR-005: Refresh Token IP Retention](../../docs/adr/005-ip-address-and-token-hash-security.md) — governs the 7-day IP retention window
