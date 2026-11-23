---
phase: 05-evaluation-and-milestone-gate
plan: 01
subsystem: sync / evaluation prerequisites
tags: [guides-index, drift-check, index-identity, sync, EVAL-01]
requires: []
provides:
  - "GUIDES_INDEX.md regenerated and committed in the Guides repo (by the owner) from Guides commit 4526500"
  - "strict drift check green (guides_index_drift 0)"
  - "index identity (guides_commit_sha, content hashes, build ids) that later eval runs compare against"
affects: [05-11 golden drafting, 05-03 tracer]
tech-stack:
  added: []
  patterns: ["docs-only plan: no file of this repository changes"]
key-files:
  created:
    - .planning/phases/05-evaluation-and-milestone-gate/05-01-SUMMARY.md
  modified: []
key-decisions:
  - "Full publish chosen by the owner (publish_mode published); executor ran no publish and no local-only sync"
patterns-established: []
requirements-completed: []
metrics:
  duration: "n/a (continuation after human checkpoint)"
  completed: 2026-11-22
status: complete
actuals:
  tokens: 0
  tasks: 3
  commits: 0
plan_head_before: 0f0a9e84e6e0d87157f5ec9bbd1a2121af44ffe1
plan_head_after: 0f0a9e84e6e0d87157f5ec9bbd1a2121af44ffe1
---

# Phase 5 Plan 01: Guides index refresh and index identity Summary

GUIDES_INDEX.md regenerated from Guides commit 4526500, committed and published by the owner, strict drift check green (exit 0, drift 0), compose `artifacts` volume rebuilt, and the index identity recorded below.

## Index identity (05-01)

- guides_commit_sha: 3cabe681fe76987928ac97df3daec339260085cc
- compose_content_hash: 55ce792552d8480dd5cdf5f0925c9b637adeec7ef2150c016929e2cd6bb8131b
- compose_build_id: 20261122T094743Z-55ce792552d8
- host_content_hash: cb01e4d6dfba18dbe9699b07443567db54afe3abcf494a835870091effb9d62d
- host_build_id: 20261122T094558Z-cb01e4d6dfba
- publish_mode: published

`git diff --name-only 4526500 3cabe681fe76987928ac97df3daec339260085cc` in the Guides repository prints exactly:

```
GUIDES_INDEX.md
```

`git merge-base --is-ancestor 4526500 HEAD` exits 0 and the Guides working tree is clean.

### Run counts (both runs)

| Run | pages_seen | pages_processed | pages_denied | chunks | video_links | guides_index_drift |
|-----|-----------|-----------------|--------------|--------|-------------|--------------------|
| strict drift check (throwaway dir) | 23 | 22 | 1 | 2800 | 2529 | 0 |
| compose sync (`artifacts` volume) | 23 | 22 | 1 | 2800 | 2529 | 0 |
| host `./artifacts` (the owner's full publish) | 23 | n/a | 1 | 2800 | 2529 | 0 |

Compose and strict runs share content_hash 55ce7925...; the host `./artifacts` hash cb01e4d6... differs because the full publish rewrote video links to the bucket (assumption A-01-3). guides_commit_sha, page set and chunk count are identical across all three, which is what golden drafting needs.

## What was done

1. Task 1 (earlier agent): GUIDES_INDEX.md regenerated in the Guides working tree from 4526500; no other Guides file changed.
2. Task 2 (checkpoint): the owner committed it in the Guides repo (3cabe681fe76), pushed to origin/master, and ran the full publish from the repo root (exit 0, new mcp-server revision forced). Reply was "committed; published".
3. Task 3: rebuilt the `ai-buddy-test` image (05-02 changed locks), ran `python -m buddy_sync run --strict` with `ARTIFACT_DIR=/tmp/strict-artifacts` (exit 0), refreshed the compose volume with `docker compose run --rm sync` (exit 0), read the host manifest.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Strict drift check needed `HANDBOOK_DIR` and `REDACT_PAGE_FILES` passed explicitly**
- **Found during:** Task 3, step 2
- **Issue:** The repo `.env` defines neither `REDACT_PAGE_FILES` (as the checkpoint response stated) nor the container-side `HANDBOOK_DIR`. The first strict run exited 1 with `invalid or missing environment variables: HANDBOOK_DIR`; no artifact was produced.
- **Fix:** Added `-e REDACT_PAGE_FILES=<denylisted page file name> -e HANDBOOK_DIR=/handbook` after `--env-file .env` on the `docker run`. For compose, `REDACT_PAGE_FILES` was set in the shell environment of the command. `.env` was never read or printed.
- **Files modified:** none
- **Commit:** n/a

Publish step 1 (local-only sync) was skipped as planned because publish_mode is `published`.

## Auth gates

None for the executor. The gcloud-authenticated publish was the owner's action at the Task 2 checkpoint.

## Commit accounting

`files_modified` is empty by design (the only edited file lives in the Guides repository, committed by the owner there). Measured `commits:` before this SUMMARY commit is 0 and no code changed, which is legitimate for a docs-only plan. The SUMMARY commit is the only commit this plan lands in this repository.

## Known Stubs

None.

## Threat Flags

None. T-05-01 to T-05-03 mitigated: the executor committed and pushed nothing in the Guides repository, ran no publish, and this SUMMARY holds only SHAs, hashes, build ids, counts and the publish mode (no page text, no page titles, no project id).

## Self-Check: PASSED

- 05-01-SUMMARY.md exists with `## Index identity (05-01)` and six key lines.
- Guides commit 3cabe681fe76 is a descendant of 4526500; recorded guides_commit_sha equals the Guides HEAD.
- `buddy_sync run --strict` exit 0.
