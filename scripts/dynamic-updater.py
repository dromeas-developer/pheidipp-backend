#!/usr/bin/env python3
"""
Generate:
docs/implementation/implemented-state.md

Purpose:
Current executable state of the platform.

Emit facts only.
No architecture inference.
No documentation synthesis.
"""

from __future__ import annotations

import argparse
import ast
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "docs/implementation/implemented-state.md"

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
EVENT_CALL_NAMES = {"publish", "emit", "create_event", "publish_event"}
DB_CALL_NAMES = {"commit", "flush"}
PYDANTIC_BASES = {"BaseModel", "pydantic.BaseModel"}
SKIP_DIRS = {".git", ".mypy_cache", ".opencode", ".pytest_cache", ".ruff_cache", ".venv", "__pycache__", "docs", "scripts", "venv"}


@dataclass(frozen=True)
class ClassDef:
    name: str
    node: ast.ClassDef
    file: Path


@dataclass(frozen=True)
class ModelInfo:
    name: str
    table: str | None
    file: Path
    bases: tuple[str, ...]


@dataclass(frozen=True)
class SchemaInfo:
    name: str
    file: Path


@dataclass(frozen=True)
class RepositoryInfo:
    name: str
    file: Path
    model: str


@dataclass(frozen=True)
class ServiceInfo:
    name: str
    file: Path
    dependencies: tuple[str, ...]


@dataclass(frozen=True)
class RouteInfo:
    method: str
    path: str
    file: Path
    function: str
    line: int
    router: str | None


@dataclass(frozen=True)
class EventProducer:
    file: Path
    class_name: str | None
    function: str
    line: int
    call: str
    event_type: str
    transaction_position: str


@dataclass(frozen=True)
class TransactionBoundary:
    file: Path
    class_name: str | None
    function: str
    line: int
    call: str


@dataclass(frozen=True)
class RouterInfo:
    name: str
    file: Path
    prefix: str


@dataclass(frozen=True)
class RegistrationInfo:
    file: str
    imports: tuple[str, ...]
    includes: tuple[str, ...]


@dataclass(frozen=True)
class MigrationInfo:
    file: Path
    revision: str | None
    down_revision: str | None


@dataclass(frozen=True)
class GitState:
    commit: str
    dirty: bool
    changed_files: tuple[str, ...]


@dataclass(frozen=True)
class ChangeSet:
    base_commit: str
    current_commit: str
    added: tuple[str, ...]
    modified: tuple[str, ...]
    deleted: tuple[str, ...]
    touched_areas: tuple[str, ...]


@dataclass(frozen=True)
class DependencyChange:
    added: tuple[str, ...]
    updated: tuple[str, ...]
    removed: tuple[str, ...]


class FileCache:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._contexts: dict[Path, FileContext] = {}

    def py_files(self, folder: Path) -> list[Path]:
        if not folder.exists():
            return []

        files = []
        for path in folder.rglob("*.py"):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            files.append(path)

        return sorted(files)

    def context(self, path: Path) -> FileContext:
        if path not in self._contexts:
            rel = path.relative_to(self.root)
            self._contexts[path] = FileContext(path, str(rel))
        return self._contexts[path]

    def text(self, path: Path) -> str:
        return self.context(path).text

    def tree(self, path: Path) -> ast.Module | None:
        return self.context(path).tree


class FileContext:
    def __init__(self, path: Path, rel: str) -> None:
        self.path = path
        self.rel = rel
        self._text: str | None = None
        self._tree: ast.Module | None | bool = False

    @property
    def text(self) -> str:
        if self._text is None:
            self._text = self.path.read_text(encoding="utf-8")
        return self._text

    @property
    def tree(self) -> ast.Module | None:
        if self._tree is False:
            try:
                self._tree = ast.parse(self.text)
            except Exception:
                self._tree = None
        return self._tree


def join_paths(*parts: str | None) -> str:
    clean = [part.strip("/") for part in parts if part and part.strip("/")]
    return f"/{'/'.join(clean)}" if clean else ""


def rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root))


def run_command(
    args: list[str],
    *,
    cwd: Path,
    timeout: float | None = None,
    strip: bool = True,
) -> str:
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception as exc:
        return f"unavailable: {type(exc).__name__}: {exc}"

    output = result.stdout or result.stderr
    if result.returncode != 0 and output:
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if lines and lines[0].startswith("Traceback"):
            return f"unavailable: {lines[-1]}"
        return f"unavailable: {lines[0]}"
    return output.strip() if strip else output


def decode_porcelain_path(path: str) -> str:
    if path.startswith('"') and path.endswith('"'):
        try:
            return ast.literal_eval(path)
        except Exception:
            return path[1:-1]
    return path


def is_excluded_path(path: str) -> bool:
    return any(part in SKIP_DIRS for part in Path(path).parts)


def untracked_files(root: Path, path: str, excluded_dirs: set[str] | None = None) -> list[str]:
    excluded_dirs = excluded_dirs or set()
    full_path = root / path

    if not full_path.exists():
        return [f"?? {path}"]

    if not full_path.is_dir():
        return [f"?? {path}"]

    files = []
    for file in full_path.rglob("*"):
        if file.is_file() and not any(part in excluded_dirs for part in file.parts):
            files.append(f"?? {rel(file, root)}")

    return sorted(files)


def git_state(root: Path) -> GitState:
    commit = run_command(["git", "rev-parse", "--short", "HEAD"], cwd=root)
    status = run_command(["git", "status", "--porcelain"], cwd=root, strip=False)

    if status.startswith("unavailable:"):
        return GitState(commit=commit or "unknown", dirty=False, changed_files=())

    files = []
    for line in status.splitlines():
        if not line:
            continue

        code = line[:2]
        path = decode_porcelain_path(line[3:])

        if code.startswith(("R", "C")) and " -> " in path:
            path = path.split(" -> ", 1)[1]

        if is_excluded_path(path):
            continue

        if code == "??":
            files.extend(
                file.replace("?? ", " N ", 1)
                for file in untracked_files(root, path, SKIP_DIRS)
            )
        else:
            files.append(f"{code} {path}")

    return GitState(
        commit=commit or "unknown",
        dirty=bool(files),
        changed_files=tuple(sorted(set(files))),
    )


def resolve_output_path(output: str, cwd: Path) -> Path | None:
    if output == "-":
        return None

    path = Path(output)
    return path if path.is_absolute() else (cwd / path).resolve()


def parse_output_commit(path: Path) -> str | None:
    if not path.exists():
        return None

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    for index, line in enumerate(lines[:-1]):
        if line.strip() == "Commit:":
            value = lines[index + 1].strip()
            return value or None

    return None


def previous_output_commit(root: Path, output: Path | None) -> str | None:
    candidates = []
    if output is not None:
        candidates.append(output)
    candidates.extend(
        [
            root / ".opencode/instructions/implemented-state.md",
            root / "docs/implementation/implemented-state.md",
        ]
    )

    seen = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue

        if resolved in seen:
            continue
        seen.add(resolved)

        value = parse_output_commit(resolved)
        if value:
            return value

    return None


def parent_commit(root: Path, current_commit: str) -> str:
    if not current_commit or current_commit.startswith("unavailable:"):
        return "unknown"

    return run_command(["git", "rev-parse", "--short", f"{current_commit}^"], cwd=root) or current_commit


def classify_status_code(code: str, path: str) -> tuple[str, str] | None:
    normalized = code.strip()

    if normalized.startswith(("A", "C")):
        return "added", path
    if normalized.startswith("D"):
        return "deleted", path
    if normalized.startswith(("M", "R", "T", "U")):
        return "modified", path

    return None


def committed_changes(root: Path, base_commit: str, current_commit: str) -> list[tuple[str, str]]:
    if not base_commit or not current_commit:
        return []
    if base_commit == current_commit:
        return []
    if base_commit.startswith("unavailable:") or current_commit.startswith("unavailable:"):
        return []

    status = run_command(
        ["git", "diff", "--name-status", "--find-renames", base_commit, current_commit],
        cwd=root,
        strip=False,
    )
    if status.startswith("unavailable:"):
        return []

    changes = []
    for line in status.splitlines():
        if not line.strip():
            continue

        fields = line.split("\t")
        code = fields[0].strip().split()[0]
        path = fields[-1] if len(fields) > 1 else ""
        if is_excluded_path(path):
            continue

        classified = classify_status_code(code, path)
        if classified:
            changes.append(classified)

    return changes


def status_changes(root: Path) -> list[tuple[str, str]]:
    status = run_command(["git", "status", "--porcelain"], cwd=root, strip=False)
    if status.startswith("unavailable:"):
        return []

    changes = []
    for line in status.splitlines():
        if not line:
            continue

        code = line[:2]
        path = decode_porcelain_path(line[3:])

        if code.startswith(("R", "C")) and " -> " in path:
            path = path.split(" -> ", 1)[1]

        if is_excluded_path(path):
            continue

        if code == "??":
            for file in untracked_files(root, path, SKIP_DIRS):
                changes.append(("added", file[3:]))
            continue

        classified = classify_status_code(code, path)
        if classified:
            changes.append(classified)

    return changes


def touched_areas(paths: set[str]) -> tuple[str, ...]:
    rules = [
        ("models", ("app/models",)),
        ("repositories", ("app/repositories",)),
        ("services", ("app/services",)),
        ("api", ("app/api",)),
        ("app", ("app",)),
        ("schemas", ("app/schemas",)),
        ("core", ("app/core",)),
        ("migrations", ("alembic/versions", "migrations/versions")),
        ("opencode", (".opencode",)),
        ("architecture", ("docs/architecture",)),
        ("implementation", ("docs/implementation",)),
        ("release-plan", ("docs/release-plan",)),
        ("adr", ("docs/adr",)),
        ("scripts", ("scripts",)),
        ("requirements", ("requirements.txt",)),
        ("docs", ("docs",)),
    ]

    areas = set()
    for path in paths:
        normalized = path.strip("/")
        matched = False
        for area, prefixes in rules:
            if any(normalized == prefix or normalized.startswith(f"{prefix}/") for prefix in prefixes):
                areas.add(area)
                matched = True
                break

        if not matched:
            areas.add("root" if "/" not in normalized else "other")

    order = {area: index for index, (area, _) in enumerate(rules)}
    order["root"] = len(order)
    order["other"] = len(order) + 1
    return tuple(sorted(areas, key=lambda area: (order.get(area, len(order)), area)))


def change_set(root: Path, output: Path | None = None) -> ChangeSet:
    current_commit = run_command(["git", "rev-parse", "--short", "HEAD"], cwd=root) or "unknown"
    previous_commit = previous_output_commit(root, output)
    base_commit = previous_commit or parent_commit(root, current_commit)

    if previous_commit and previous_commit != current_commit:
        base_commit = previous_commit
    elif previous_commit == current_commit:
        base_commit = parent_commit(root, current_commit)

    changes = committed_changes(root, base_commit, current_commit) + status_changes(root)
    buckets = {
        "added": set(),
        "modified": set(),
        "deleted": set(),
    }

    for action, path in changes:
        if action in buckets:
            buckets[action].add(path)

    touched = touched_areas(buckets["added"] | buckets["modified"] | buckets["deleted"])
    return ChangeSet(
        base_commit=base_commit,
        current_commit=current_commit,
        added=tuple(sorted(buckets["added"])),
        modified=tuple(sorted(buckets["modified"])),
        deleted=tuple(sorted(buckets["deleted"])),
        touched_areas=touched,
    )


def parse_requirement_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    if stripped.startswith("-"):
        return None

    comment_index = stripped.find("#")
    if comment_index != -1:
        stripped = stripped[:comment_index].strip()

    if not stripped:
        return None

    package_end = 0
    while package_end < len(stripped):
        char = stripped[package_end]
        if char.isalnum() or char in {"-", "_", ".", "["}:
            package_end += 1
            continue
        break

    package = stripped[:package_end].strip("[]").split("[", 1)[0]
    version_spec = stripped[package_end:].strip()
    return package.lower(), version_spec


def parse_requirements_txt(content: str) -> dict[str, str]:
    dependencies = {}
    for line in content.splitlines():
        parsed = parse_requirement_line(line)
        if parsed:
            package, version_spec = parsed
            dependencies[package] = version_spec

    return dependencies


def diff_dependencies(old: dict[str, str], new: dict[str, str]) -> DependencyChange:
    added = []
    updated = []
    removed = []

    for package, new_spec in sorted(new.items()):
        if package not in old:
            added.append(f"{package}{new_spec}")
        elif old[package] != new_spec:
            old_spec = old[package] or "unversioned"
            new_value = new_spec or "unversioned"
            updated.append(f"{package} ({old_spec} → {new_value})")

    for package in sorted(set(old) - set(new)):
        removed.append(package)

    return DependencyChange(
        added=tuple(added),
        updated=tuple(updated),
        removed=tuple(removed),
    )


def git_file_content(root: Path, commit: str, filepath: str) -> str | None:
    if not commit or commit.startswith("unavailable:"):
        return None

    value = run_command(["git", "show", f"{commit}:{filepath}"], cwd=root, timeout=10.0)
    if value.startswith("unavailable:"):
        return None
    return value


def dependency_drift(root: Path, base_commit: str) -> DependencyChange | None:
    if not base_commit or base_commit.startswith("unavailable:"):
        return None

    requirements_file = root / "requirements.txt"
    if not requirements_file.exists():
        return None

    try:
        current = requirements_file.read_text(encoding="utf-8")
    except OSError:
        return None

    base = git_file_content(root, base_commit, "requirements.txt")
    old = parse_requirements_txt(base or "")
    new = parse_requirements_txt(current)

    if old == new:
        return None

    return diff_dependencies(old, new)


def format_dependency_changes(changes: DependencyChange | None) -> str:
    if not changes:
        return "requirements.txt\nNo changes detected"

    return f"""requirements.txt
Added:
{format_list(changes.added)}

Updated:
{format_list(changes.updated)}

Removed:
{format_list(changes.removed)}"""


def format_service_facts(services: list[ServiceInfo], root: Path) -> str:
    return "\n".join(f"- {svc.name} — {rel(svc.file, root)}" for svc in services) or "- none"


def should_show_wiring_dependency(dependency: str) -> bool:
    ignored = {
        "AsyncSession",
        "None",
        "str",
        "int",
        "float",
        "bool",
        "UUID",
        "date",
        "datetime",
        "dict",
        "list",
        "tuple",
        "set",
        "Literal",
    }
    return dependency not in ignored and " | None" not in dependency


def format_service_wiring(services: list[ServiceInfo]) -> str:
    if not services:
        return "- no services detected"

    lines = []
    for index, service in enumerate(sorted(services, key=lambda svc: svc.name)):
        dependencies = sorted(
            dep for dep in service.dependencies if should_show_wiring_dependency(dep)
        )
        lines.append(service.name)
        if not dependencies:
            lines.append(" └── none")
        else:
            # Limit to 10 deps if needed
            shown = dependencies[:10]
            for dep_index, dependency in enumerate(shown):
                is_last = (dep_index == len(shown) - 1) and len(dependencies) <= 10
                prefix = " └── " if is_last else " ├── "
                lines.append(f"{prefix}{dependency}")

            if len(dependencies) > 10:
                lines.append(f" ... +{len(dependencies) - 10} more")

        if index < len(services) - 1:
            lines.append("")

    return "\n".join(lines)


def compute_registration_status(
    registrations: list[RegistrationInfo],
    models: list[ModelInfo],
    enums: list[ModelInfo],
    schemas: list[SchemaInfo],
    repositories: list[RepositoryInfo],
    services: list[ServiceInfo],
    routes: list[RouteInfo],
    api_dependencies: set[str],
) -> dict[str, str]:
    imports_by_file = {registration.file: set(registration.imports) for registration in registrations}
    expected = {
        "app/models/__init__.py": {model.name for model in models} | {model.name for model in enums},
        "app/schemas/__init__.py": {schema.name for schema in schemas},
        "app/repositories/__init__.py": {repo.name for repo in repositories},
        "app/services/__init__.py": {service.name for service in services},
        "app/api/__init__.py": api_dependencies,
        "app/api/v1/__init__.py": {route.router for route in routes if route.router},
    }
    labels = {
        "app/models/__init__.py": "models",
        "app/schemas/__init__.py": "schemas",
        "app/repositories/__init__.py": "repositories",
        "app/services/__init__.py": "services",
        "app/api/__init__.py": "api dependencies",
        "app/api/v1/__init__.py": "routers",
    }

    status = {}
    for file_path, expected_items in expected.items():
        actual = imports_by_file.get(file_path)
        if actual is None:
            state = "missing"
        elif expected_items <= actual:
            state = "complete"
        else:
            state = "partial"
        status[labels[file_path]] = state

    return status


def format_registration_status(status: dict[str, str]) -> str:
    return "\n".join(f"{module}: {state}" for module, state in sorted(status.items()))


def alembic_current(root: Path, timeout: float) -> str:
    value = run_command(["alembic", "current"], cwd=root, timeout=timeout)
    return value or "unknown"


def class_defs(cache: FileCache, folder: Path) -> list[ClassDef]:
    out = []

    for file in cache.py_files(folder):
        tree = cache.tree(file)
        if not tree:
            continue

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                out.append(ClassDef(node.name, node, file))

    return sorted(out, key=lambda x: (x.file, x.name))


def unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return "?"


def literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def inherits(node: ast.ClassDef) -> tuple[str, ...]:
    result = []

    for base in node.bases:
        if isinstance(base, ast.Name):
            result.append(base.id)
        elif isinstance(base, ast.Attribute):
            result.append(unparse(base))
        elif isinstance(base, ast.Subscript):
            result.append(unparse(base.value))

    return tuple(sorted(set(result)))


def is_enum_class(node: ast.ClassDef) -> bool:
    return any(base == "Enum" or base.endswith(".Enum") for base in inherits(node))


def is_model_class(node: ast.ClassDef) -> bool:
    return any(base in {"Base", "DeclarativeBase"} for base in inherits(node))


def is_pydantic_model(node: ast.ClassDef) -> bool:
    return any(base in PYDANTIC_BASES or base.endswith(".BaseModel") for base in inherits(node))


def table_name(node: ast.ClassDef) -> str | None:
    for stmt in node.body:
        if not isinstance(stmt, ast.Assign):
            continue
        if any(isinstance(t, ast.Name) and t.id == "__tablename__" for t in stmt.targets):
            return literal_string(stmt.value)
    return None


def models(cache: FileCache, root: Path) -> tuple[list[ModelInfo], list[ModelInfo]]:
    entities = []
    enums = []

    for item in class_defs(cache, root / "app/models"):
        if is_enum_class(item.node):
            enums.append(ModelInfo(item.name, None, item.file, inherits(item.node)))
        elif is_model_class(item.node):
            entities.append(ModelInfo(item.name, table_name(item.node), item.file, inherits(item.node)))

    return sorted(entities, key=lambda x: x.name), sorted(enums, key=lambda x: x.name)


def schemas(cache: FileCache, root: Path) -> list[SchemaInfo]:
    result = []

    for item in class_defs(cache, root / "app/schemas"):
        if is_pydantic_model(item.node):
            result.append(SchemaInfo(item.name, item.file))

    return sorted(result, key=lambda x: (x.file, x.name))


def imported_names(tree: ast.Module) -> dict[str, str]:
    names: dict[str, str] = {}

    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if alias.name == "*":
                    continue
                local = alias.asname or alias.name.split(".")[-1]
                names[local] = f"{node.module}.{alias.name}"

        elif isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                names[local] = alias.name

    return names


def name_from_call_func(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return unparse(func)


def target_from_call_func(func: ast.AST) -> str:
    if isinstance(func, ast.Attribute):
        return unparse(func)
    return name_from_call_func(func)


def name_refs(node: ast.AST) -> set[str]:
    refs: set[str] = set()

    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            refs.add(child.id)
        elif isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name):
            refs.add(child.value.id)

    return refs


def select_model_refs(call: ast.Call, model_names: set[str]) -> set[str]:
    refs: set[str] = set()

    for arg in call.args:
        for ref in name_refs(arg):
            if ref in model_names:
                refs.add(ref)

    for keyword in call.keywords:
        for ref in name_refs(keyword.value):
            if ref in model_names:
                refs.add(ref)

    return refs


def repository_model(
    name: str,
    node: ast.ClassDef,
    tree: ast.Module,
    model_names: set[str],
) -> str:
    candidates: set[str] = set()

    for child in ast.walk(node):
        if isinstance(child, ast.Call) and name_from_call_func(child.func) == "select":
            candidates.update(select_model_refs(child, model_names))

        if isinstance(child, ast.Assign) and isinstance(child.value, ast.Name):
            if child.value.id in model_names:
                candidates.add(child.value.id)

    if not candidates and name.endswith("Repository"):
        prefix = name[: -len("Repository")]
        if prefix in model_names:
            candidates.add(prefix)

    if len(candidates) == 1:
        return next(iter(candidates))

    if candidates:
        return ", ".join(sorted(candidates))

    imports = imported_names(tree)
    imported_models = sorted(
        local for local, fq in imports.items() if fq.startswith("app.models.") and local in model_names
    )
    if len(imported_models) == 1:
        return imported_models[0]

    return "unknown"


def repositories(cache: FileCache, root: Path) -> list[RepositoryInfo]:
    entities, _ = models(cache, root)
    model_names = {model.name for model in entities}
    result = []

    for item in class_defs(cache, root / "app/repositories"):
        tree = cache.tree(item.file)
        if not tree:
            continue

        result.append(
            RepositoryInfo(
                name=item.name,
                file=item.file,
                model=repository_model(item.name, item.node, tree, model_names),
            )
        )

    return sorted(result, key=lambda x: (x.file, x.name))


def init_function(node: ast.ClassDef) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for child in node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == "__init__":
            return child
    return None


def constructor_annotations(init: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    annotations = []

    for arg in list(init.args.args[1:]) + list(init.args.kwonlyargs):
        if arg.annotation:
            annotations.append(unparse(arg.annotation))

    return annotations


def instantiated_dependencies(node: ast.ClassDef) -> list[str]:
    dependencies = []

    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue

        name = name_from_call_func(child.func)
        if name.endswith("Repository") or name.endswith("Service"):
            dependencies.append(name)

    return sorted(set(dependencies))


def services(cache: FileCache, root: Path) -> list[ServiceInfo]:
    out = []

    for item in class_defs(cache, root / "app/services"):
        init = init_function(item.node)
        if not init:
            continue

        dependencies = constructor_annotations(init)
        dependencies.extend(instantiated_dependencies(item.node))

        if not dependencies:
            continue

        out.append(
            ServiceInfo(
                name=item.name,
                file=item.file,
                dependencies=tuple(sorted(set(dependencies))),
            )
        )

    return sorted(out, key=lambda x: (x.file, x.name))


def router_prefix_kw(call: ast.Call) -> str:
    for keyword in call.keywords:
        if keyword.arg == "prefix":
            return literal_string(keyword.value) or unparse(keyword.value)
    return ""


def router_infos(cache: FileCache, root: Path) -> tuple[dict[str, RouterInfo], dict[str, set[str]]]:
    routers: dict[str, RouterInfo] = {}
    parents: dict[str, set[str]] = {}

    for file in cache.py_files(root / "app/api"):
        tree = cache.tree(file)
        if not tree:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if not isinstance(target, ast.Name):
                        continue

                    if (
                        isinstance(node.value, ast.Call)
                        and name_from_call_func(node.value.func) == "APIRouter"
                    ):
                        routers[target.id] = RouterInfo(
                            name=target.id,
                            file=file,
                            prefix=router_prefix_kw(node.value),
                        )

            if isinstance(node, ast.Call) and name_from_call_func(node.func) == "include_router":
                child = None
                parent = None

                if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                    parent = node.func.value.id

                if node.args:
                    child = literal_string(node.args[0]) or (
                        node.args[0].id if isinstance(node.args[0], ast.Name) else None
                    )

                for keyword in node.keywords:
                    if keyword.arg == "router" and isinstance(keyword.value, ast.Name):
                        child = keyword.value.id

                if child and parent:
                    parents.setdefault(child, set()).add(parent)

    return routers, parents


def resolve_router_prefixes(
    router: str,
    routers: dict[str, RouterInfo],
    parents: dict[str, set[str]],
    visiting: set[str] | None = None,
) -> set[str]:
    visiting = visiting or set()

    if router in visiting:
        return {routers[router].prefix} if router in routers else {""}

    visiting.add(router)
    info = routers.get(router)
    local_prefix = info.prefix if info else ""

    if router not in parents or not parents[router]:
        visiting.remove(router)
        return {local_prefix}

    prefixes = set()
    for parent in parents[router]:
        for parent_prefix in resolve_router_prefixes(parent, routers, parents, visiting):
            prefixes.add(join_paths(parent_prefix, local_prefix))

    visiting.remove(router)
    return prefixes or {local_prefix}


def route_decorator(decorator: ast.AST) -> tuple[str, str, str | None] | None:
    call = decorator if isinstance(decorator, ast.Call) else None
    func = call.func if call else decorator

    if not isinstance(func, ast.Attribute):
        return None

    method = func.attr.lower()
    if method not in HTTP_METHODS:
        return None

    router = func.value.id if isinstance(func.value, ast.Name) else None
    path = ""

    if call and call.args:
        path = literal_string(call.args[0]) or unparse(call.args[0])
    elif call:
        for keyword in call.keywords:
            if keyword.arg == "path":
                path = literal_string(keyword.value) or unparse(keyword.value)
                break

    return method.upper(), path, router


def routes(cache: FileCache, root: Path) -> list[RouteInfo]:
    routers, parents = router_infos(cache, root)
    result = []

    for file in cache.py_files(root / "app/api"):
        tree = cache.tree(file)
        if not tree:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            for decorator in node.decorator_list:
                route = route_decorator(decorator)
                if not route:
                    continue

                method, path, router = route
                prefix = ""

                if router and router in routers:
                    prefixes = resolve_router_prefixes(router, routers, parents)
                    prefix = sorted(prefixes, key=len, reverse=True)[0]

                result.append(
                    RouteInfo(
                        method=method,
                        path=join_paths(prefix, path),
                        file=file,
                        function=node.name,
                        line=node.lineno,
                        router=router,
                    )
                )

    return sorted(result, key=lambda x: (x.path, x.method, x.file, x.function))


class CallContextVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.class_stack: list[str] = []
        self.function_stack: list[str] = []

    def current_class(self) -> str | None:
        return self.class_stack[-1] if self.class_stack else None

    def current_function(self) -> str:
        return self.function_stack[-1] if self.function_stack else "<module>"

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()


class EventVisitor(CallContextVisitor):
    def __init__(self, file: Path) -> None:
        super().__init__()
        self.file = file
        self.events: list[EventProducer] = []

    def visit_Call(self, node: ast.Call) -> None:
        name = name_from_call_func(node.func)
        if name in EVENT_CALL_NAMES:
            event_type = "unknown"
            for keyword in node.keywords:
                if keyword.arg == "event_type":
                    event_type = literal_string(keyword.value) or unparse(keyword.value)
                    break

            self.events.append(
                EventProducer(
                    file=self.file,
                    class_name=self.current_class(),
                    function=self.current_function(),
                    line=getattr(node, "lineno", 0),
                    call=name,
                    event_type=event_type,
                    transaction_position="uncommitted",
                )
            )

        self.generic_visit(node)


class TransactionVisitor(CallContextVisitor):
    def __init__(self, file: Path) -> None:
        super().__init__()
        self.file = file
        self.boundaries: list[TransactionBoundary] = []

    def visit_Call(self, node: ast.Call) -> None:
        name = name_from_call_func(node.func)
        if name in DB_CALL_NAMES:
            self.boundaries.append(
                TransactionBoundary(
                    file=self.file,
                    class_name=self.current_class(),
                    function=self.current_function(),
                    line=getattr(node, "lineno", 0),
                    call=target_from_call_func(node.func),
                )
            )

        self.generic_visit(node)


def events(cache: FileCache, root: Path, commits: list[TransactionBoundary], flushes: list[TransactionBoundary]) -> list[EventProducer]:
    result = []

    for file in cache.py_files(root / "app"):
        tree = cache.tree(file)
        if not tree:
            continue

        visitor = EventVisitor(file)
        visitor.visit(tree)
        result.extend(visitor.events)

    return correlate_events_transactions(result, commits, flushes)


def correlate_events_transactions(
    events: list[EventProducer],
    commits: list[TransactionBoundary],
    flushes: list[TransactionBoundary],
) -> list[EventProducer]:
    transactions = commits + flushes
    by_scope: dict[tuple[Path, str | None, str], list[TransactionBoundary]] = defaultdict(list)

    for boundary in transactions:
        by_scope[(boundary.file, boundary.class_name, boundary.function)].append(boundary)

    result = []
    for event in events:
        key = (event.file, event.class_name, event.function)
        position = event_transaction_position(event.line, by_scope.get(key, []))
        result.append(
            EventProducer(
                file=event.file,
                class_name=event.class_name,
                function=event.function,
                line=event.line,
                call=event.call,
                event_type=event.event_type,
                transaction_position=position,
            )
        )

    return sorted(result, key=lambda x: (x.file, x.line, x.function, x.call, x.event_type))


def event_transaction_position(event_line: int, transactions: list[TransactionBoundary]) -> str:
    if not transactions:
        return "uncommitted"

    if any(transaction.line > event_line for transaction in transactions):
        return "after_commit"

    if any(transaction.line < event_line for transaction in transactions):
        return "before_commit"

    return "unknown"


def transaction_boundaries(cache: FileCache, root: Path) -> tuple[list[TransactionBoundary], list[TransactionBoundary]]:
    commits = []
    flushes = []

    for file in cache.py_files(root / "app"):
        tree = cache.tree(file)
        if not tree:
            continue

        visitor = TransactionVisitor(file)
        visitor.visit(tree)

        for boundary in visitor.boundaries:
            if boundary.call.endswith(".commit"):
                commits.append(boundary)
            elif boundary.call.endswith(".flush"):
                flushes.append(boundary)

    commits = sorted(commits, key=lambda x: (x.file, x.line, x.function))
    flushes = sorted(flushes, key=lambda x: (x.file, x.line, x.function))
    return commits, flushes


def import_names(tree: ast.Module) -> tuple[str, ...]:
    names = []

    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.append(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.asname or alias.name.split(".")[0])

    return tuple(sorted(set(names)))


def included_routers(tree: ast.Module) -> tuple[str, ...]:
    routers = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or name_from_call_func(node.func) != "include_router":
            continue

        if node.args:
            if isinstance(node.args[0], ast.Name):
                routers.append(node.args[0].id)
            else:
                routers.append(literal_string(node.args[0]) or unparse(node.args[0]))

        for keyword in node.keywords:
            if keyword.arg == "router" and isinstance(keyword.value, ast.Name):
                routers.append(keyword.value.id)

    return tuple(sorted(set(routers)))


def registrations(cache: FileCache, root: Path) -> list[RegistrationInfo]:
    targets = [
        "app/models/__init__.py",
        "app/schemas/__init__.py",
        "app/repositories/__init__.py",
        "app/services/__init__.py",
        "app/api/__init__.py",
        "app/api/v1/__init__.py",
    ]

    found = []

    for target in targets:
        file = root / target
        if not file.exists():
            continue

        tree = cache.tree(file)
        if not tree:
            found.append(RegistrationInfo(target, (), ()))
            continue

        found.append(
            RegistrationInfo(
                file=target,
                imports=import_names(tree),
                includes=included_routers(tree),
            )
        )

    return found


def api_dependency_exports(cache: FileCache, root: Path) -> set[str]:
    file = root / "app/api/deps.py"
    if not file.exists():
        return set()

    tree = cache.tree(file)
    if not tree:
        return set()

    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            names.add(node.name)

        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    names.add(target.id)

    return names


def missing_exports(
    registrations: list[RegistrationInfo],
    models: list[ModelInfo],
    enums: list[ModelInfo],
    schemas: list[SchemaInfo],
    repositories: list[RepositoryInfo],
    services: list[ServiceInfo],
    routes: list[RouteInfo],
    api_dependencies: set[str],
) -> dict[str, list[str]]:
    imports_by_file = {registration.file: set(registration.imports) for registration in registrations}
    checks = {
        "app/models/__init__.py": {model.name for model in models} | {model.name for model in enums},
        "app/schemas/__init__.py": {schema.name for schema in schemas},
        "app/repositories/__init__.py": {repo.name for repo in repositories},
        "app/services/__init__.py": {service.name for service in services},
        "app/api/__init__.py": api_dependencies,
        "app/api/v1/__init__.py": {route.router for route in routes if route.router},
    }

    missing = {}
    for file_path, expected in checks.items():
        actual = imports_by_file.get(file_path, set())
        absent = sorted(expected - actual)
        if absent:
            missing[file_path] = absent

    return missing


def revision_from_alembic_current(value: str) -> str | None:
    if not value or value.startswith("unavailable:") or value in {"unknown", "skipped"}:
        return None
    return value.split()[0]


def latest_migration_revision(migrations: list[MigrationInfo]) -> str | None:
    for migration in reversed(migrations):
        if migration.revision:
            return migration.revision
    return None


def db_revision_with_fallback(raw_revision: str, migrations: list[MigrationInfo]) -> str:
    if not raw_revision.startswith("unavailable:"):
        return raw_revision

    latest = latest_migration_revision(migrations)
    if not latest:
        return raw_revision

    return f"{latest} (head) [fallback: latest migration file]"


def migration_pending(current_revision: str, migrations: list[MigrationInfo]) -> str:
    if not migrations:
        return "no"

    latest = migrations[-1].revision
    if not latest:
        return "unknown"

    if current_revision.startswith("unavailable:") or "fallback:" in current_revision:
        return "unknown"

    current = revision_from_alembic_current(current_revision)
    if not current:
        return "unknown"

    return "yes" if current != latest else "no"


def dependency_signals(cache: FileCache, root: Path) -> tuple[list[str], list[str]]:
    async_session_files = []
    repository_dependencies = []

    for file in cache.py_files(root / "app"):
        tree = cache.tree(file)
        if not tree:
            continue

        imports = imported_names(tree)
        if any(fq.endswith("AsyncSession") for fq in imports.values()):
            async_session_files.append(rel(file, root))

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id.endswith("Repository"):
                    repository_dependencies.append(f"{rel(file, root)}: {node.func.id}")

    return sorted(set(async_session_files)), sorted(set(repository_dependencies))


def assignment_value(tree: ast.Module, name: str) -> ast.AST | None:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                return node.value

        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == name:
                return node.value

    return None


def assignment_string(tree: ast.Module, name: str) -> str | None:
    value = assignment_value(tree, name)
    if not value:
        return None

    if isinstance(value, ast.Constant):
        if isinstance(value.value, str):
            return value.value
        if value.value is None:
            return None

    if isinstance(value, (ast.Tuple, ast.List)):
        values = [literal_string(item) or unparse(item) for item in value.elts]
        return ", ".join(values)

    return unparse(value)


def migrations(cache: FileCache, root: Path) -> list[MigrationInfo]:
    dirs = [root / "alembic/versions", root / "migrations/versions"]
    files = []

    for directory in dirs:
        if not directory.exists():
            continue
        files.extend(directory.glob("*.py"))

    records = []
    for file in sorted(files):
        tree = cache.tree(file)
        if not tree:
            continue

        records.append(
            MigrationInfo(
                file=file,
                revision=assignment_string(tree, "revision"),
                down_revision=assignment_string(tree, "down_revision"),
            )
        )

    return sort_migrations(records)[:10]


def sort_migrations(records: list[MigrationInfo]) -> list[MigrationInfo]:
    by_revision = {record.revision: record for record in records if record.revision}
    children: dict[str | None, list[str]] = {}
    indegree: dict[str, int] = {}

    for record in records:
        if not record.revision:
            continue

        parents = split_down_revision(record.down_revision)
        indegree[record.revision] = len(parents)
        for parent in parents:
            children.setdefault(parent, []).append(record.revision)

    queue = sorted(rev for rev, degree in indegree.items() if degree == 0)
    ordered: list[str] = []

    while queue:
        revision = queue.pop(0)
        ordered.append(revision)

        for child in sorted(children.get(revision, [])):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)

    ordered.extend(sorted(set(indegree) - set(ordered)))
    return [by_revision[revision] for revision in ordered if revision in by_revision]


def split_down_revision(value: str | None) -> list[str | None]:
    if not value:
        return [None]
    return [part.strip() for part in value.split(",") if part.strip()]


def snapshot_reliability() -> str:
    return """Overall Confidence: HIGH

| Section | Confidence | Coverage | Limitations |
|---------|-----------|----------|-------------|
| Models | HIGH | All .py files in app/models | — |
| Enums | HIGH | All .py files in app/models | — |
| Schemas | HIGH | All .py files in app/schemas | — |
| Repositories | HIGH | All .py files in app/repositories | — |
| Services | MEDIUM | Constructor + instantiation scanning | Does not detect injected dependencies |
| Routes | MEDIUM | Static APIRouter decorators only | Dynamic routers not detected |
| Events | MEDIUM | AST publish detection | Same-function tracking only |
| Transaction Boundaries | MEDIUM | AST commit/flush detection | Same-function tracking only |
| Registrations | HIGH | __init__.py import analysis | Does not verify runtime usage |
| Migrations | HIGH | Migration file parsing | Does not verify database state |
| Dependency Drift | HIGH | requirements.txt diff | Does not check transitive dependencies |"""


def format_list(values: list[str] | tuple[str, ...], empty: str = "- none") -> str:
    return "\n".join(f"- {value}" for value in values) if values else empty


def format_missing_exports(missing: dict[str, list[str]]) -> str:
    if not missing:
        return "- none"

    return "\n".join(
        f"- {file_path}: Missing [{', '.join(items)}]"
        for file_path, items in sorted(missing.items())
    )


def format_change_set(change: ChangeSet) -> str:
    return f"""## Change Set

Base Commit:
{change.base_commit}

Current Commit:
{change.current_commit}

Files Added:
{format_list(change.added)}

Files Modified:
{format_list(change.modified)}

Files Deleted:
{format_list(change.deleted)}

Touched Areas:
{format_list(change.touched_areas)}"""


def generate(*, root: Path, output: Path | None = None, skip_db: bool = False, alembic_timeout: float = 30.0) -> str:
    cache = FileCache(root)
    change = change_set(root, output)

    entities, enums = models(cache, root)
    schemas_list = schemas(cache, root)
    repos = repositories(cache, root)
    svc = services(cache, root)
    api = routes(cache, root)
    migr = migrations(cache, root)
    regs = registrations(cache, root)
    api_dependencies = api_dependency_exports(cache, root)
    missing = missing_exports(regs, entities, enums, schemas_list, repos, svc, api, api_dependencies)
    registration_status = compute_registration_status(
        regs, entities, enums, schemas_list, repos, svc, api, api_dependencies
    )
    dependency_changes = dependency_drift(root, change.base_commit)
    commits, flushes = transaction_boundaries(cache, root)
    ev = events(cache, root, commits, flushes)
    async_files, repo_deps = dependency_signals(cache, root)
    raw_db_revision = "skipped" if skip_db else alembic_current(root, alembic_timeout)
    db_revision = db_revision_with_fallback(raw_db_revision, migr)
    pending_migrations = migration_pending(db_revision, migr)

    return f"""# implemented-state

{format_change_set(change)}

Generated:
{datetime.now(timezone.utc).isoformat()} UTC

Current DB Revision:
{db_revision}

Python Files Scanned:
{len(cache.py_files(root / "app"))}

---

## Verified Facts

### Domain Layer

Entities:
{format_list([f"{model.name} ({model.table or 'unknown table'}) — {rel(model.file, root)}" for model in entities])}

Enums:
{format_list([f"{model.name} — {rel(model.file, root)}" for model in enums])}

### Persistence Layer

Repositories:
{format_list([f"{repo.name} -> {repo.model} ({rel(repo.file, root)})" for repo in repos])}

Migrations:
{format_list([migration_label(m, root) for m in migr])}

### Service Layer

Services:
{format_service_facts(svc, root)}

### API Surface

Public API:
{format_list([f"{route.method} {route.path} ({rel(route.file, root)}:{route.line} {route.function}, router={route.router or 'unknown'})" for route in api])}

### Contracts

{format_list([f"{schema.name} — {rel(schema.file, root)}" for schema in schemas_list])}

### Registrations

{format_registration_sections(regs)}

---

## Derived Signals

### Dependency Changes

{format_dependency_changes(dependency_changes)}

### Service Wiring

{format_service_wiring(svc)}

### Registration Status

{format_registration_status(registration_status)}

### Event Producers

{format_list([f"{rel(event.file, root)}:{event.line} {scope(event)} {event.call} -> {event.event_type} [{event.transaction_position}]" for event in ev])}

### Transaction Boundaries

Commits:
{format_list([f"{rel(b.file, root)}:{b.line} {scope(b)} {b.call}" for b in commits])}

Flushes:
{format_list([f"{rel(b.file, root)}:{b.line} {scope(b)} {b.call}" for b in flushes])}

### Observed Runtime Structure

AsyncSession imports:
{format_list(async_files)}

Repository dependencies:
{format_list(repo_deps)}

### Execution Readiness

Current Revision:
{db_revision}

Migration Pending:
{pending_migrations}

Missing Exports:
{format_missing_exports(missing)}

### Snapshot Reliability

{snapshot_reliability()}
"""


def scope(item: EventProducer | TransactionBoundary) -> str:
    if item.class_name:
        return f"{item.class_name}.{item.function}"
    return item.function


def format_service_sections(services: list[ServiceInfo], root: Path) -> str:
    sections = []

    for service in services:
        sections.append(
            "\n".join(
                [
                    f"{service.name}",
                    f"File: {rel(service.file, root)}",
                    "Dependencies:",
                    format_list(service.dependencies),
                ]
            )
        )

    return "\n\n".join(sections)


def format_registration_sections(registrations: list[RegistrationInfo]) -> str:
    sections = []

    for registration in registrations:
        lines = [registration.file]
        lines.append(f"Imports: {', '.join(registration.imports) if registration.imports else 'none'}")
        if registration.includes:
            lines.append(f"Includes: {', '.join(registration.includes)}")
        sections.append("\n".join(f"- {line}" for line in lines))

    return "\n\n".join(sections)


def migration_label(migration: MigrationInfo, root: Path) -> str:
    revision = migration.revision or "unknown revision"
    down = migration.down_revision or "none"
    return f"{revision} (down: {down}) — {rel(migration.file, root)}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate an observable implementation-state snapshot for the implementation-architect agent."
    )
    parser.add_argument("--root", type=Path, default=ROOT, help="Project root.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUT),
        help="Output path. Use '-' for stdout.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the snapshot without writing it.")
    parser.add_argument("--skip-db", action="store_true", help="Skip alembic current.")
    parser.add_argument(
        "--alembic-timeout",
        type=float,
        default=30.0,
        help="Timeout in seconds for alembic current.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    output = resolve_output_path(args.output, Path.cwd())
    content = generate(
        root=root,
        output=output,
        skip_db=args.skip_db,
        alembic_timeout=args.alembic_timeout,
    )

    if args.dry_run or args.output == "-":
        print(content)
        return

    if output is None:
        raise SystemExit("--output - can only be used with --dry-run")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    print(f"Generated {output}")


if __name__ == "__main__":
    main()
