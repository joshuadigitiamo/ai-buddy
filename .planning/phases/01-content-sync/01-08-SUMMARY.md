---
phase: 01-content-sync
plan: 08
subsystem: sync
tags: [guides, scene-maps, video-links, local-source, cross-repo, redaction]

requires:
  - phase: 01-07
    provides: buddy_sync CLI, guides-index command, strict drift check, video map resolver
provides:
  - "tests/unit/buddy_sync/test_guides_local.py: local-only check of the real Guides checkout (skipped unless GUIDES_LOCAL_DIR is set)"
  - "Guides repo commit 810efdd: sections.yaml for mcp-servers (21 entries) and multi-agent-design (52 entries), generated GUIDES_INDEX.md, gitignore negation for out/durations.json, both durations.json files"
  - "Measured D-18 false-positive counts for the redaction rules over the Guides text"
affects: [01-11, phase-02]

plan_head_before: e0d9fa395db4292cd818c712074716e8085a2b95
plan_head_after: 1b75f49e5ce1aa4b3af6b3e07abbfe530848cff3

actuals:
  tokens: 1450
  tasks: 2
  commits: 1

tech-stack:
  added: []
  patterns:
    - "Scene maps reference guide headings verbatim; strict sync turns a stale heading into VideoMapError instead of a silent wrong link"
    - "Cross-repo edits stay uncommitted until the owner reviews them (blocking-human checkpoint)"

key-files:
  created:
    - tests/unit/buddy_sync/test_guides_local.py
  modified: []

key-decisions:
  - "Each sections.yaml entry was drafted from the scene's narration and checked against the guide heading; 6 scenes unmapped in the first draft were added after review, and all 68 original entries were confirmed correct"
  - "Scenes that narrate no single section stay unmapped (titles, chapter intros, level intros, recaps, the whole-turn overview)"
  - "Item-2 optional decisions: Joshua gave none, so the defaults apply (no extra REDACT_EMAIL_ALLOW_DOMAINS; non-image attachment links keep their URL per D-17; text above a guide's first ## may stay unindexed)"

requirements-completed: [SYNC-04, SYNC-06, GUIDE-01]

coverage:
  - id: D1
    description: "Real Guides checkout resolves to scene-linked chunks: 17 guide files selected, every sections.yaml entry resolves without VideoMapError, each mapped guide has at least 5 scene links, no GUIDES_INDEX.md drift in strict mode"
    requirement: SYNC-04
    verification:
      - kind: test
        ref: "tests/unit/buddy_sync/test_guides_local.py (GUIDES_LOCAL_DIR=/guides, read-only mount): 7 passed"
        status: pass
      - kind: command
        ref: "./run-unit-tests.sh --all (317 passed, 7 skipped; the 7 skips are the local-only tests without the mount)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Each scene is mapped to the heading it narrates (D-02)"
    requirement: SYNC-06
    verification:
      - kind: command
        ref: "Joshua reviewed the Guides diff at the checkpoint; narration was re-checked against the guides for the 6 added scenes and the 68 original entries"
        status: pass
    human_judgment: true
    rationale: "Whether a scene narrates a section is a reading judgment; the resolver only proves the heading exists"
  - id: D3
    description: "Guides changes committed in the Guides repo and tracked there (3 contract files, 2 durations files)"
    requirement: GUIDE-01
    verification:
      - kind: command
        ref: "git ls-files counts: sections.yaml x2 + GUIDES_INDEX.md = 3; durations.json x2 = 2"
        status: pass
    human_judgment: false

duration: not measured (the plan paused at a human checkpoint)
completed: 2026-11-03
status: complete
---

# Phase 1 Plan 08: Guides Scene Maps and Local Check Summary

**Two real scene maps (mcp-servers 21 entries, multi-agent-design 52), a generated GUIDES_INDEX.md and the durations.json gitignore negation are committed in the Guides repo (810efdd), and a local-only test proves the real checkout resolves to scene-linked chunks with no index drift (7 passed against the mount, 317 passed with 7 skipped in the full suite).**

## Performance

- **Tasks:** 2 (1 tracer in this repo, 1 human-action checkpoint in the Guides repo)
- **Files changed in this repo:** 1 created (165 lines), outside the SUMMARY
- **Guides repo:** 1 commit, `810efdd` "Add scene maps and guide index for AI Buddy sync", pushed to origin/master

## Accomplishments

- Tracer: `test_guides_local.py` skips without `GUIDES_LOCAL_DIR`. With the mount it checks 17 selected guide files, more than 2000 chunks, no `VideoMapError`, at least 5 scene links in each of the two mapped guides, a README-video link on every chunk of a guide that has one and none on dash-row guides, a strict `GUIDES_INDEX.md` check with no drift, and one search hit with video source `scene`; it also prints per-rule redaction hit counts.
- Guides repo: `.gitignore` now ignores `videos/**/out/*` and keeps `!videos/**/out/durations.json`; both `sections.yaml`, both `out/durations.json` and the generated `GUIDES_INDEX.md` are tracked.
- Checkpoint verification (counts only): `ls-files` gave 3 for the contract files and 2 for the durations files.

## Task Commits

1. Task 1 (tracer): `1b75f49` test - local-only check of the real Guides checkout
2. Task 2 (checkpoint:human-action): commit `810efdd` in the Guides repo (not this repo). Joshua reviewed the diff and told Claude "You can commit and push", so Claude committed and pushed to origin/master. This replaces the plan's "Joshua commits himself" wording; the explicit instruction satisfies the user rule against unrequested commits.

## Map entries and unmapped scenes

Entries: mcp-servers 21, multi-agent-design 52.

| Video | Unmapped scene | Reason |
|-------|----------------|--------|
| mcp-servers | S01Title | title |
| mcp-servers | S06StatelessChapter, S15ToolsChapter, S18SecurityChapter, S24ChoosingChapter | 1-2 line chapter intros, no single section |
| mcp-servers | S27Recap | recap |
| multi-agent-design | P1S01Title, P2S01Title, P3S01Title | titles |
| multi-agent-design | P1S06McpLevel, P2S12OrchLevel, P3S10PlatformLevel, P3S17QualityLevel | level intros |
| multi-agent-design | P1S19Recap, P2S20Recap | recaps |
| multi-agent-design | P3S02Turn | overview of the whole turn, spanning sections 34 to 46 |

## Guides redaction hit counts (D-18 false-positive check)

Counts only, over the 17 selected guide files:

| Rule | Hits |
|------|------|
| high_entropy | 46 |
| labelled_secret | 10 |
| private_email | 27 |

These are probably false positives in guide examples (sample keys, placeholder addresses). Flagged for plan 01-11 and the D-18 follow-up: inspect them there and tune the rules or the allow-list if they mask real guide text. No value was printed or copied.

## Item-2 optional decisions

Joshua gave no answer, so the defaults apply: no extra `REDACT_EMAIL_ALLOW_DOMAINS` (only `digitiamo.com`), non-image attachment links keep their URL (D-17 literal), text above a guide's first `##` may stay unindexed.

## Verification

- Local test with `GUIDES_LOCAL_DIR=/guides` and a read-only Guides mount, network off: 7 passed, 0 skipped.
- `./run-unit-tests.sh --all`: 317 passed, 7 skipped (the local-only tests, since the mount is absent), 0 failed.
- Checkpoint counts: 3 contract files and 2 durations files tracked in the Guides repo.

## Deviations from Plan

**1. [Rule 3 - Blocking] Guides repo moved while the checkpoint was open**
- **Found during:** Task 2 (review)
- **Issue:** Joshua pushed 7 commits from another PC (a60b4cb..720d9d7), including 7270311 "MCP guide: add section 21 Code Mode and renumber sections 22-31". The local checkout was behind and the headings in the mcp-servers map no longer matched the guide.
- **Fix:** fast-forwarded the local Guides checkout (stashed `.gitignore`, `pull --ff-only`, re-applied the negation on top of Joshua's new Remotion ignore lines), then updated three mcp-servers headings for the renumbering: S09SdkTraps -> "24. SDKs and the Wider Ecosystem" / "24.3 FastMCP — the name collision you need to understand"; S25WrongTool -> "25. When MCP Is the Wrong Tool"; S26Decision -> "27. Decision Checklist — Should You Build a Server?".
- **Lesson:** number-prefixed headings make scene maps fragile when a guide is renumbered. Strict sync catches it as `VideoMapError`, so the drift is loud, not silent. Consider whether the contract should allow headings without the number prefix (for plan 01-11 or a later contract revision).
- **Commit:** 810efdd (Guides repo)

**2. [Rule 2 - Missing critical] Review added 6 scenes the first draft left unmapped**
- **Found during:** Task 2 (narration check against the guides)
- **Issue:** the first draft left scenes unmapped that do narrate one section.
- **Fix:** added S03Primitives -> "1. What Is MCP?" / "What a server exposes"; S09SdkTraps (see above); P1S02Layers -> "The one-paragraph version"; P1S03Kitchen -> "The one-paragraph version" / "The restaurant analogy"; P1S04Rule -> "The one-line decision rule"; P1S05Atlas -> 'What we are designing: "Atlas"'. All 68 original entries were confirmed correct.
- **Commit:** 810efdd (Guides repo)

**3. [Plan wording] Claude made the Guides commit and push**
- The plan expected Joshua to commit and said "no push needed". On his explicit instruction ("You can commit and push") Claude committed and pushed 810efdd to origin/master. Acceptance criterion "Guides HEAD unchanged by Claude" is superseded by that instruction; the tracked-file counts (3 and 2) are the check that held.

**Total deviations:** 2 auto-fixed, 1 wording change. **Impact:** none on scope; the maps are larger than the minimum of 5 entries per video.

## Authentication Gates

None. The checkpoint was a review-and-commit step, not an auth gate.

## Known Stubs

None.

## Threat Flags

None. T-01-37 (cross-repo tampering) was mitigated: the edits stayed in the working tree until Joshua reviewed the diff and gave the explicit commit instruction. T-01-SC: no package added. No `.env` value, handbook content or Wi-Fi page text was printed or copied; the redaction table holds rule names and integers only.

## Issues Encountered

- The 7 redaction-rule hit groups above need a look in plan 01-11 before the live run trusts the redaction on the Guides.
- The worktree used for this SUMMARY started from a stale base (40df727) and was fast-forwarded to `gsd/phase-01-content-sync` (687ebae) so the phase folder exists; no content was merged beyond that fast-forward.

## Requirements Tracking

The plan declares SYNC-04, SYNC-06 and GUIDE-01. Marking them in REQUIREMENTS.md, STATE.md and ROADMAP.md is left to the orchestrator for this run.

## Next Phase Readiness

Ready for 01-11 (live local run and verification): the real Guides checkout carries valid maps and a drift-free index, and the local-only test can be re-run against any future Guides update. Open items for 01-11: inspect the redaction hits, and re-run `test_guides_local.py` after any guide renumbering.

## Self-Check: PASSED

`tests/unit/buddy_sync/test_guides_local.py` exists; commit `1b75f49` is an ancestor of HEAD; measured commit count 1 for this repo (`e0d9fa3..1b75f49`); the Guides commit `810efdd` is in the other repository and was verified there by the tracked-file counts.
