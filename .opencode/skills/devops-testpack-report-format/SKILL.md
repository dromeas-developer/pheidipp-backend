---
name: devops-testpack-report-format
description: >
  Load this at the Output Format step of the Test Pack Mode protocol when
  results are ready to be written. Contains the lightweight Test Pack Mode
  report format — a re-verification pass tied to prior report RC ids.
  Loaded by p-devops only in Test Pack Mode. For Full Pipeline Mode, load
  devops-report-format instead.
---

# DevOps — Test Pack Report Format

Save report using `write` as
`reports/<plan-id>_devops_testpack_<n>.md`, where `<n>` increments per
Test Pack run for this plan (check `find_files` for prior
`_testpack_` reports to determine the next index).

For one-off/ad-hoc validation runs with no prior FAIL report and no
plan-id: use `reports/oneoff_<description>_<YYYYMMDD>.md`.

```markdown
# DevOps Test Pack Report — <plan-id> (pass <n>)
Date: <date>
Re-verifying: reports/<plan-id>_devops.md (dated <prior date>) — RC<ids>
Test execution group / scope: <as resolved in Procedure step 2>

## Result: PASS | FAIL

Tests: <n> passed / <n> failed / <n> skipped
Root causes resolved: <n> of <n> from the prior report
Root causes still open: <n> (see Root Cause Analysis below if any)

## Infrastructure Fixes

*Only present if DevOps modified test infrastructure files in this session.*

## Root Cause Analysis

*Present only if any RC from the prior report — or any new failure
surfaced during this re-run — is still failing. Use the same RC structure
as the Full Pipeline report (see `devops-report-format` skill for the full
RC entry format): Category, Owner, Confidence, Evidence, Files, Affected
failures, Suggested fix.*

## Routing Summary

*Same structure as Full Pipeline report — only for RCs still open.*

## Full Failure Detail

## Next Step
→ All prior RCs resolved and no new failures: recommend a Full Pipeline
  Mode run before promotion (Test Pack Mode does not gate the
  manifest/migration/build promotion path).
→ Some RCs still open, or new failures surfaced: route per Routing
  Summary above, same as a Full Pipeline FAIL.
```
