---
phase: 05
review: 05-REVIEW.md
titles: json
findings:
  - id: WR-04
    severity: warning
    disposition: open
    title: "Stale-feedback cleanup deletes every feedback row with a scorer name, including human or other-source ones"
  - id: IN-01
    severity: info
    disposition: open
    title: "`EVAL_LLM_BACKEND=api` is advertised but cannot work through compose"
  - id: IN-02
    severity: info
    disposition: open
    title: "`assert` used for control-flow narrowing in a runtime path"
  - id: IN-03
    severity: info
    disposition: open
    title: "`_safe_url` can raise outside the try block in preflight"
  - id: IN-04
    severity: info
    disposition: open
    title: "Duplicated constants and type aliases across modules"
  - id: IN-05
    severity: info
    disposition: open
    title: "Fixture page date assumes a plain date"
  - id: IN-06
    severity: info
    disposition: open
    title: "Dead single-character entries in the question stopword set"
  - id: IN-07
    severity: info
    disposition: open
    title: "An empty `MERIDIAN_OAUTH_TOKEN` yields a silently useless Meridian profile"
  - id: IN-08
    severity: info
    disposition: open
    title: "Duplicated and inconsistent exception branches around the traced call"
  - id: CR-01
    severity: critical
    disposition: fixed
  - id: WR-01
    severity: warning
    disposition: fixed
  - id: WR-02
    severity: warning
    disposition: fixed
  - id: WR-03
    severity: warning
    disposition: fixed
open: 9
total: 13
recorded: 2026-11-22T22:24:54.367Z
---

# Phase 05: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-04 | warning | open | - |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| IN-04 | info | open | - |
| IN-05 | info | open | - |
| IN-06 | info | open | - |
| IN-07 | info | open | - |
| IN-08 | info | open | - |
| CR-01 | critical | fixed | 05-16 (d8dda4f) (not in the current review) |
| WR-01 | warning | fixed | 05-16 (3f5ef6a) run and empty-context; 05-15 (7f92173) recall (not in the current review) |
| WR-02 | warning | fixed | 05-16 (d8dda4f, ccdb7a3, 3f5ef6a) (not in the current review) |
| WR-03 | warning | fixed | 05-15 (7f92173) (not in the current review) |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
