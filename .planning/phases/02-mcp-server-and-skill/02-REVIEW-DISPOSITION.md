---
phase: 02
review: 02-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: open
    title: "AUTH_MODE=off guard fails open on any host other than Cloud Run"
  - id: WR-02
    severity: warning
    disposition: open
    title: "Loopback prefix check on MCP_PUBLIC_BASE_URL accepts attacker-style hostnames"
  - id: WR-03
    severity: warning
    disposition: open
    title: "Gap log stores raw question text for topics the Skill declares sensitive"
  - id: WR-04
    severity: warning
    disposition: open
    title: "Tool descriptions and server instructions contradict the Skill, causing spurious gap records"
  - id: WR-05
    severity: warning
    disposition: open
    title: "OAUTH_JWT_SIGNING_KEY length is documented as 32 bytes minimum but never enforced"
  - id: IN-01
    severity: info
    disposition: open
    title: "Unbounded query, id and tried inputs"
  - id: IN-02
    severity: info
    disposition: open
    title: "Runtime image has no health check and uses floating, unhashed inputs"
  - id: IN-03
    severity: info
    disposition: open
    title: "Host/Origin allowlist omits the portless loopback origin and IPv6"
  - id: IN-04
    severity: info
    disposition: open
    title: "Verified-token cache keeps an offboarded user valid for up to five minutes"
open: 9
total: 9
recorded: 2026-11-06T22:11:28.240Z
---

# Phase 02: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | open | - |
| WR-02 | warning | open | - |
| WR-03 | warning | open | - |
| WR-04 | warning | open | - |
| WR-05 | warning | open | - |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| IN-04 | info | open | - |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
