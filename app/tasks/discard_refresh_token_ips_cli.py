"""Cron-driver entry point for the refresh-token IP discard task.

Invoked by ``scripts/discard-refresh-token-ips.sh`` and any future
orchestrator that wants to run the task as a one-shot CLI process.

The module-level ``main()`` parses a single optional ``--retention-days``
flag, runs the async task, prints the affected row count to stdout, and
exits with code 0 on success or 1 on any exception. The exit code is
the contract cron uses to detect failure.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.tasks.discard_refresh_token_ips import discard_refresh_token_ips


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="app.tasks.discard_refresh_token_ips_cli",
        description=(
            "Discard RefreshToken.ip_address values older than the "
            "ADR-005 retention window. Idempotent."
        ),
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=None,
        help=(
            "Override the retention window in days. Defaults to "
            "RefreshTokenRepository.IP_RETENTION_DAYS (= 7)."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        discarded = asyncio.run(discard_refresh_token_ips(retention_days=args.retention_days))
    except Exception as exc:  # noqa: BLE001 — surface any failure as exit 1 to cron
        print(f"discard-refresh-token-ips: FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"discard-refresh-token-ips: discarded {discarded} row(s).")
    return 0


if __name__ == "__main__":  # pragma: no cover — explicit CLI guard
    raise SystemExit(main())
