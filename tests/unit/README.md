# tests/unit/

## Purpose
Verifies individual units in isolation — services, repositories, schemas, and utility
functions — with the database session and all external dependencies mocked. No real
database connection is made; each test constructs its own mocks for `AsyncSession`,
collaborator services, and repositories.

## Contents
### Authentication
| File | Covers |
|---|---|
| `test_auth_service.py` | AuthService: register (atomic 4-entity creation + event, rollback on failure), login (success, wrong password 401, nonexistent email constant-time), rotate_refresh_token (rotation, old token rejected, expired rejected, unknown rejected, atomicity rollback) |
| `test_auth_schemas.py` | RegisterRequest password blank/whitespace validation, AuthResponse and TokenPairResponse token_hash and hashed_password exclusion |

### Utilities & Security
| File | Covers |
|---|---|
| `test_ip_utils.py` | truncate_ip (IPv4 /24 CIDR, IPv6 /64 CIDR, None/empty/invalid/non-string) |
| `test_token_security.py` | safe_extra forbidden-key filtering (token_hash, hashed_password, ip_address, unknown keys), RefreshTokenRepository.discard_old_ips (7-day cutoff, zero-row case) |

## Mock Boundaries
- DB session (AsyncSession) is mocked; no `db_session` fixture needed — see `tests/MOCKING_CONTRACT.md` for the authoritative layer table
- Collaborator services and repositories are replaced with `MagicMock`/`AsyncMock` inline in each test file
- No shared conftest.py at this level; fixtures are defined per-file
