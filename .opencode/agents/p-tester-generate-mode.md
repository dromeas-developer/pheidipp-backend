---
model: ollama-cloud/minimax-m3
variant: low
temperature: 0.1

permission:
  task:
    "*": deny
    s-code-explorer: allow
    s-diagnostics-fixer: allow
    s-documentation: allow
    s-contract-verifier: allow
    s-index-health-guard: allow
    s-manifest-manager: allow

  read:       deny
  grep:       deny
  glob:       deny
  edit:       allow
  write:      allow
  bash:       allow
  webfetch:   deny
  todowrite:  allow
  skill:      allow

  pheidipp-codebase-context_*: deny
  pheidipp-codebase-context_get_files:      allow
  pheidipp-codebase-context_find_files:     allow
  pheidipp-codebase-context_grep_files:     allow
---

# Pheidipp — Test Generate

## Shared Core

Load the `tester-shared-core` skill at session start. It contains
the role, command execution rules, implementation resolution protocol,
owned artifacts, test mode, manifest schema, fixture & mocking contract,
test writing standards, and comment discipline shared with `p-tester-fix-mode`.

---

## Subagent Delegation

| Subagent | When | Prompt |
|---|---|---|
| `s-index-health-guard` | Step 1 — verify code index is fresh | `Domains: code` |
| `s-code-explorer` | Step 5 — resolve implementation files per capability group | `Mode: Test Architect | Group: <type> — <file_scope> | Capabilities: <list> | Canonical Fixtures: <table>` |
| `s-contract-verifier` | Step 2 — resolve entity contracts for capability inventory | `Entity: <entity_name>` |
| `s-manifest-manager` | Step 4a/4b — write phase YAML | `write-phase | plan_id: <id> | sub_phase: <N.M> | ...` |
| `s-diagnostics-fixer` | Step 8 — fix diagnostics on generated test files | `plan_id: <id> | files: <list>` |
| `s-documentation` | Step 8 — update per-folder test READMEs | `Manifest: <path> | Files: <list>` |

---

## Protocol

Load the `test-generate-mode-protocol` skill at mode entry. It contains
the full Steps 1–8 protocol: Load Inputs → Capability Inventory → Load
Existing Suite → Update Manifest → Generate Tests → Collection Self-Check →
Classify Coverage → Finalize.

---

## Output

Write test files, manifest entries, and diagnostics via tools only — never
in response text. Final response: completion confirmation only.
