#!/usr/bin/env python3
"""
scripts/mcp-reindex.py — Manually trigger a full codebase reindex.

Usage (from the backend project root):
    python scripts/mcp-reindex.py
    python scripts/mcp-reindex.py --mcp-dir ../../mcp-server  # custom path
"""

import argparse
import sys
from pathlib import Path

MCP_DIR_DEFAULT = Path(__file__).resolve().parents[2] / "mcp-server"

EXTENSIONS = [
    ".py", ".ts", ".tsx", ".js", ".jsx",
    ".md", ".json", ".toml", ".yaml", ".yml",
    ".dockerfile", ".env", ".sh",
]
EXCLUDE = ["node_modules", ".git", "dist", "build", "__pycache__", ".venv", "plans", "scripts"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Force a full codebase reindex.")
    parser.add_argument("--mcp-dir", default=str(MCP_DIR_DEFAULT),
                        help=f"Path to the mcp-server directory (default: {MCP_DIR_DEFAULT})")
    args = parser.parse_args()

    mcp_dir = Path(args.mcp_dir).resolve()
    if not (mcp_dir / "indexing.py").exists():
        print(f"[error] indexing.py not found in: {mcp_dir}", file=sys.stderr)
        print("        Use --mcp-dir to specify the correct path.", file=sys.stderr)
        return 1

    sys.path.insert(0, str(mcp_dir))
    from indexing import build_index  # noqa: E402

    project_path = str(Path(__file__).resolve().parents[1])  # backend root
    storage_dir  = str(mcp_dir / "storage")

    print(f"[reindex] Project : {project_path}")
    print(f"[reindex] Storage : {storage_dir}")
    print(f"[reindex] Building index — this may take a while …")

    build_index(project_path, storage_dir, EXTENSIONS, EXCLUDE)

    print("[reindex] Done ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())