---
name: coder-comment-discipline
description: >
  Load when writing or editing any source file. Defines what comments
  are never allowed, when inline comments are justified, and the rule of
  thumb for self-documenting code. Loaded on demand by p-coder-batch-mode
  and p-coder-fix-mode when writing files.
---

The codebase is self-documenting through clear naming and folder-level
READMEs. Inline comments are a last resort, not a default.

**Never write:**
* Comments that describe what the next line already says in code
  (`# increment counter` above `counter += 1`)
* Docstrings that restate the function name
  (`"""Get athlete by ID."""` above `def get_athlete_by_id(...)`)
* Section header comments (`# === Database Operations ===`)
* Commented-out code — delete it; git history exists for a reason
* TODO comments — track in the BRD or issue tracker, not in source
* Closing-brace or "end of" markers (`# end for`, `# end if`)
* Import-section labels (`# Standard library`, `# Third party`)

**Write only when the code alone would mislead:**
* Module-level docstring: one line, only if the filename doesn't make
  the module's purpose obvious
* Class docstring for public classes: one line, only if the class name
  doesn't fully convey its responsibility
* Inline comment: only when the code is genuinely surprising — a
  non-obvious algorithm, a business rule a reader would miss, or a
  deliberate deviation from a pattern that looks like a mistake
* `# noqa` and `# type: ignore` as required by tooling

**Never:**
* Docstrings on private methods (`_method_name`)
* Multi-line docstrings anywhere — if it needs more than one line, it
  belongs in the folder's `README.md` (maintained by `p-doc-writer`),
  not in the file

**Rule of thumb:** if you catch yourself writing a comment to explain
"what" the code does, delete the comment and rename the variable or
function. If you catch yourself writing a comment to explain "why" the
code is shaped a certain way, ask whether the folder README already
covers the architectural context. If not, flag it for `p-doc-writer` to
capture there — do not inline it.
