"""
Generates .opencode/instructions/dynamic.md

Run:  python scripts/update_context.py
Make: make context
Auto: git pre-commit hook on models/, migrations/, worker/, agents/ changes
"""

import ast
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# scripts/ is inside backend/ — ROOT is backend/
ROOT = Path(__file__).resolve().parent.parent

# Ensure backend/ is on sys.path so `from app.x import y` works
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# .opencode/ lives at the project root (parent of backend/)
OUT = ROOT / ".opencode/instructions/dynamic-context.md"


def alembic_head() -> str:
    try:
        r = subprocess.run(
            ["alembic", "current"],
            capture_output=True, text=True, cwd=ROOT
        )
        for line in r.stdout.splitlines():
            if line.strip() and not line.startswith("INFO"):
                return line.strip()
    except Exception as e:
        print(f"⚠️ alembic_head failed: {e}", file=sys.stderr)
    return "unknown"


def schema() -> str:
    try:
        from app.db.base import Base  # corrected import path

        # Import all models so they register with Base.metadata
        import app.models  # noqa: F401 — side effect: registers all models

        lines = []
        for name, table in sorted(Base.metadata.tables.items()):
            lines.append(f"\n**{name}**")
            for col in table.columns:
                flags = []
                if col.primary_key:
                    flags.append("PK")
                if col.foreign_keys:
                    fk = next(iter(col.foreign_keys))
                    flags.append(f"FK→{fk.target_fullname}")
                if not col.nullable and not col.primary_key:
                    flags.append("NOT NULL")
                flag = f" `[{', '.join(flags)}]`" if flags else ""
                lines.append(f"  - `{col.name}` {col.type}{flag}")

        if not lines:
            return "  (no tables found — check app/models/__init__.py imports)"

        return "\n".join(lines)

    except Exception as e:
        return f"⚠️ Could not introspect schema: {e}"


def modules() -> str:
    layers = [
        "api", "models", "schemas", "services",
        "repositories", "worker", "agents", "core"
    ]
    output = []
    for layer in layers:
        d = ROOT / "app" / layer
        if not d.exists():
            continue
        files = [f.name for f in sorted(d.glob("*.py"))]
        if files:
            output.append(f"\n**app/{layer}/**")
            for f in files[:20]:
                output.append(f"  - `{f}`")
            if len(files) > 20:
                output.append(f"  - ... and {len(files) - 20} more")
    return "\n".join(output)


def api_endpoints() -> str:
    api_dir = ROOT / "app/api"
    if not api_dir.exists():
        return "  (none)"
    endpoints = []
    for f in api_dir.rglob("*.py"):
        try:
            tree = ast.parse(f.read_text())
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for decorator in node.decorator_list:
                        if hasattr(decorator, "func"):
                            method = getattr(decorator.func, "attr", "")
                            if method in {"get", "post", "put", "patch", "delete"}:
                                path = ""
                                if decorator.args:
                                    try:
                                        path = decorator.args[0].value
                                    except Exception:
                                        pass
                                endpoints.append(
                                    f"  - {method.upper()} {path} → "
                                    f"`{f.relative_to(ROOT)}:{node.name}`"
                                )
        except Exception:
            continue
    if len(endpoints) > 30:
        endpoints = endpoints[:30] + [f"  - ... and {len(endpoints) - 30} more"]
    return "\n".join(endpoints) or "  (none)"


def arq_jobs() -> str:
    d = ROOT / "app/worker"
    if not d.exists():
        return "  (none)"
    jobs = []
    for f in d.rglob("*.py"):
        try:
            tree = ast.parse(f.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.AsyncFunctionDef):
                    if node.args.args and node.args.args[0].arg == "ctx":
                        jobs.append(f"  - `{node.name}()` — `{f.relative_to(ROOT)}`")
        except Exception:
            continue
    return "\n".join(jobs) or "  (none)"


def agents() -> str:
    d = ROOT / "app/agents"
    if not d.exists():
        return "  (none)"
    found = []
    for f in d.rglob("*.py"):
        try:
            if "StateGraph" in f.read_text():
                found.append(f"  - `{f.relative_to(ROOT)}`")
        except Exception:
            continue
    return "\n".join(found) or "  (none)"


def recent_migrations() -> str:
    versions_dir = ROOT / "alembic" / "versions"
    if not versions_dir.exists():
        return "  (none)"
    files = sorted(
        versions_dir.glob("*.py"),
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )[:5]
    lines = []
    for f in files:
        parts = f.stem.split("_", 1)
        rev = parts[0][:8]
        msg = parts[1].replace("_", " ") if len(parts) > 1 else f.stem
        lines.append(f"  - `{rev}` — {msg}")
    return "\n".join(lines) or "  (none)"

def relationships() -> str:
    try:
        from app.db.base import Base
        import app.models  # noqa

        lines = []
        for name, table in sorted(Base.metadata.tables.items()):
            fks = [
                f"  - `{col.name}` → `{next(iter(col.foreign_keys)).target_fullname}`"
                for col in table.columns
                if col.foreign_keys
            ]
            if fks:
                lines.append(f"\n**{name}**")
                lines.extend(fks)
        return "\n".join(lines) or "  (none)"
    except Exception as e:
        return f"⚠️ {e}"

def generate() -> str:
    return f"""\
# dynamic-context

## Alembic Head
`{alembic_head()}`

## Recent Migrations
{recent_migrations()}

## Database Schema
{schema()}

## Foreign Keys & Relationships
{relationships()}

## API Endpoints
{api_endpoints()}

## Modules
{modules()}

## Background Jobs (ARQ)
{arq_jobs()}

## LangGraph Agents
{agents()}
"""


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(generate())
    print(f"✓ Generated {OUT.relative_to(ROOT)}")  # ← ROOT not PROJECT_ROOT

if __name__ == "__main__":
    main()