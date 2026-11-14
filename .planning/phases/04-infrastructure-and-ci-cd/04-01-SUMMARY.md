---
phase: 04-infrastructure-and-ci-cd
plan: 01
subsystem: infra
tags: [supply-chain, google-cloud-storage, meridian, decision-gate, pip-pin]

requires:
  - phase: 03-google-chat-bot
    provides: approved Meridian commit (03-01 gate), gate-plan pattern
provides:
  - "google-cloud-storage==3.17.1 pinned in services/mcp_server/requirements.txt (GcsArtifactStore, video upload)"
  - "deploy/meridian.version: single source of the approved Meridian commit (D-14)"
  - "Six recorded phase decisions (billing_mode, coverage_inheritance, sections_authoring, video_fetch, token_chain, org_policy) that later plans read by key"
  - "04-CONTEXT.md amendments block recording D-17 and D-18 interpretations"
affects: [04-06, 04-07, 04-08, 04-09, 04-10, 04-11, 04-12, 04-13, 04-14]

actuals:
  tokens: 1100
  tasks: 3
  commits: 1
plan_head_before: 94c45f7b1079d3c525b6e6a54a11f661e1f49c98
plan_head_after: d4ae2bc633c1bc51d857a57b5ec94a72bb0c7340

tech-stack:
  added: [google-cloud-storage==3.17.1]
  patterns:
    - "Gate plan settles open questions once; later plans cite the SUMMARY decision key"
    - "Amendments are additive in 04-CONTEXT.md; no locked decision line is edited"
    - "One-line commit file (deploy/meridian.version) as the single source for the Meridian build source"

key-files:
  created:
    - deploy/meridian.version
  modified:
    - services/mcp_server/requirements.txt
    - .planning/phases/04-infrastructure-and-ci-cd/04-CONTEXT.md

key-decisions:
  - "billing_mode (a): request-based billing on both services; 04-13 measures a slow question and asks Joshua again on a stall (keeps INFRA-04)"
  - "coverage_inheritance (a): literal D-18 fallback, a section with no sections.yaml entry gets start 0 (keeps D-18)"
  - "sections_authoring (a): Claude drafts five sections.yaml, Joshua commits them with five durations.json; eight guides without durations stay at 0 (interprets D-18)"
  - "video_fetch (a): Joshua downloads release videos into .cache/videos on the host (interprets D-17)"
  - "token_chain (b): separate fresh claude login seeds the Cloud Run bucket; local volume keeps its own chain (keeps D-12)"
  - "org_policy: (yes) project ai-buddy-dev is under the digitiamo.com organization (IDs in docs/internal/gcp-project.md); billing linked; org policies may apply to 04-08 bootstrap and 04-13 (information)"

patterns-established:
  - "Decision lines: `- <key>: (<letter>) <choice> — <relation>`; amendment lines in CONTEXT cite the same key and letter"

requirements-completed: [INFRA-04]

coverage:
  - id: D1
    description: "google-cloud-storage==3.17.1 approved at the blocking legitimacy gate, pinned once, and installed in the test image without breaking pin agreement tests"
    requirement: "INFRA-04"
    verification:
      - kind: unit
        ref: "./run-unit-tests.sh --single-file test_repo_layout.py tests/unit (11 passed, incl. test_requirements_are_pinned and test_shared_pins_agree)"
        status: pass
    human_judgment: false
  - id: D2
    description: "deploy/meridian.version holds exactly the approved 40-hex Meridian commit"
    requirement: "INFRA-04"
    verification:
      - kind: other
        ref: "grep -cxE '[0-9a-f]{40}' deploy/meridian.version returns 1"
        status: pass
    human_judgment: false
  - id: D3
    description: "Six open questions answered by Joshua and recorded with option letters and relation to locked text; D-17 and D-18 interpretations written additively to 04-CONTEXT.md"
    requirement: "INFRA-04"
    verification: []
    human_judgment: true
    rationale: "Decisions are Joshua's recorded answers; whether each line states the intent he meant is his judgment, not a test assertion"

duration: 25min
completed: 2026-11-14
status: complete
---

# Phase 4 Plan 01: Supply-chain and decision gate Summary

**Approved google-cloud-storage==3.17.1 pin, the single-file Meridian commit (deploy/meridian.version), and six recorded phase decisions with additive D-17/D-18 amendments in 04-CONTEXT.md**

## Performance

- **Duration:** about 25 min (resumed executor session, Tasks 3 onward; Tasks 1 and 2 were answered checkpoints)
- **Completed:** 2026-11-14T11:46:15Z
- **Tasks:** 3 (2 checkpoints answered, 1 auto)
- **Files modified:** 3 (1 created, 2 modified)

## Supply chain (04-01 Task 1)

- Approved by Joshua at the blocking legitimacy checkpoint ("approved") before any install or image build that included the pin.
- Pin: `google-cloud-storage==3.17.1` (newest release; 3.17.0 and 3.16.0 are older). Checked on 2026-11-14 with `docker run --rm python:3.12-slim pip index versions google-cloud-storage` (no install into a project image). Today is before 2026-12-14, so no re-check was needed.
- Meridian commit: `cafdcf780f1b40c8f0dee17481132f47b4cbb353` (approved at 03-01, built by Phase 4 CI per D-14), stored in `deploy/meridian.version`.

## Phase decisions (04-01 Task 2)

Joshua replied "defaults; org: Personal". "Defaults" accepts options 1a, 2a, 3a, 4a and 5b. The org answer was first read as `no`; the orchestrator then checked the GCP console on 2026-11-14 and corrected it to `yes`: project `ai-buddy-dev` (ID `ai-buddy-dev`) is under the `digitiamo.com` organization (IDs in docs/internal/gcp-project.md) with a billing account linked. The console fact is what is recorded.

- billing_mode: (a) request-based billing on both services; 04-13 measures a deliberately slow question and asks Joshua again if it stalls — keeps INFRA-04
- coverage_inheritance: (a) a section with no `sections.yaml` entry gets start 0 of the current part, no new heuristic — keeps D-18
- sections_authoring: (a) Claude drafts the five `sections.yaml` (a2a-protocol, airflow, big-data-frameworks, deep-agents, langsmith) in the local Guides working tree; Joshua reviews and commits them with the five `durations.json` in the Guides repo; the eight guides without `durations.json` stay at the 0-offset fallback and are listed as "no durations" — interprets D-18
- video_fetch: (a) Joshua runs `gh release download videos --repo <owner>/Guides --dir .cache/videos` on the host with his own login; `upload-videos` reads `Guides/videos/*/out/` and `.cache/videos` — interprets D-17
- token_chain: (b) a fresh, separate `claude` login seeds the Cloud Run bucket; the local `meridian-claude` volume keeps its own chain and the compose live profile stays writable; kind always mounts a read-only copy — keeps D-12
- org_policy: (yes) project ai-buddy-dev is under the digitiamo.com organization (IDs in docs/internal/gcp-project.md); billing linked; org policies may apply to 04-08 bootstrap and 04-13 — information

## Accomplishments

- Added the one new Python pin (`google-cloud-storage==3.17.1`) after the human legitimacy gate; the test image installs it through the existing `-r services/mcp_server/requirements.txt` line and `test_shared_pins_agree` still passes.
- Created `deploy/meridian.version` as the single source for the Meridian commit that compose, kind, Cloud Run YAML and CI will read or be tested against.
- Recorded six decisions and wrote the `## Amendments (04-01 checkpoint)` block (D-17 and D-18 interpretations) additively; no original decision line changed.

## Task Commits

1. **Task 1: Legitimacy gate** - no commit (checkpoint, answered "approved")
2. **Task 2: Six open questions** - no commit (checkpoint, answered "defaults; org: Personal")
3. **Task 3: Record decisions, pin google-cloud-storage, write deploy/meridian.version** - `d4ae2bc` (chore)

**Plan metadata:** recorded in the docs commit that follows this file (docs: complete plan).

## Files Created/Modified

- `deploy/meridian.version` - the approved 40-hex Meridian commit, one line
- `services/mcp_server/requirements.txt` - appended `google-cloud-storage==3.17.1`
- `.planning/phases/04-infrastructure-and-ci-cd/04-CONTEXT.md` - additive `<amendments>` block (8 lines added, 0 deleted)

## Decisions Made

The six decisions are listed under "Phase decisions (04-01 Task 2)" above. Key points for later plans: request-based billing stays until 04-13 measures otherwise; the token chain is separate per environment; Guides data work (five `sections.yaml`, `durations.json` commits, video download) lands in 04-14 and the Guides repo.

## Deviations from Plan

None - plan executed exactly as written.

Note: Task 3 acceptance criterion 4 (six decision lines in this SUMMARY) is satisfied by this file; the criterion could only be checked after the SUMMARY was written, which the plan's own ordering requires.

## Issues Encountered

None. The project works directly on `main` (project memory, no phase branches); the commit used a normal `git commit` with hooks.

## User Setup Required

None - no external service configuration required in this plan. Later plans carry the Joshua-side steps (video download in 04-14, Guides commits, fresh `claude` login for the Cloud Run bucket seed in 04-08).

## Next Phase Readiness

- 04-06 to 04-09 can read `deploy/meridian.version`; 04-10 onward read the decision keys above.
- RESEARCH tool-version validity ends 2026-12-14; plans executed later than that should re-check versions.

## Self-Check: PASSED

- FOUND: deploy/meridian.version, services/mcp_server/requirements.txt (1 `google-cloud-storage==` line), 04-CONTEXT.md amendments heading (1)
- FOUND: commit d4ae2bc on main
- `./run-unit-tests.sh --single-file test_repo_layout.py tests/unit`: 11 passed (test_shared_pins_agree present)

---
*Phase: 04-infrastructure-and-ci-cd*
*Completed: 2026-11-14*
