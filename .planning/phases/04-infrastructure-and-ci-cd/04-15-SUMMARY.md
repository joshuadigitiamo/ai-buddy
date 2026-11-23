---
phase: 04-infrastructure-and-ci-cd
plan: 15
subsystem: infra
tags: [guarda, video-offset, media-fragment, live-diagnosis, gap-closure, sc5]

requires:
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-11 storage.cloud.google.com video URLs in the index"
  - phase: 04-infrastructure-and-ci-cd
    provides: "04-14 scene coverage raised from 238 to 708 rows"
provides:
  - "Offline regression test pinning that a scene offset survives index -> MCP guides_search -> bot -> Chat card Guarda button, and that a fallback row yields no fragment"
  - "Hop-by-hop live record: the #t= fragment survives every hop on a scene-mapped section"
  - "Decision no-fix: 04-16 only re-runs live check 10"
affects: [04-16]

actuals:
  tokens: 1200
  tasks: 3
  commits: 1
plan_head_before: 9c99751b635859bc30a39f838084c43031eefda4
plan_head_after: 6dba386

tech-stack:
  added: []
  patterns:
    - "Characterization test over the real MCP server and the bot workflow with the placeholder bucket demo-videos"

key-files:
  created:
    - tests/unit/chat_bot/test_guarda_offset_path.py
  modified: []

key-decisions:
  - "no-fix: the 04-13 check-10 click was most likely a fallback row with no offset; every live hop keeps the fragment"

requirements-completed: [INFRA-04]

coverage:
  - id: D1
    description: "A scene offset from the index reaches the Guarda button URL as #t=125, a fallback row has no fragment, and the converted card keeps the fragment"
    requirement: INFRA-04
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_guarda_offset_path.py#test_scene_offset_reaches_the_guarda_button"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_guarda_offset_path.py#test_fallback_row_has_no_offset_in_the_guarda_button"
        status: pass
    human_judgment: false
  - id: D2
    description: "Live hops keep #t= and playback starts at the offset on a scene-mapped section"
    requirement: INFRA-04
    verification: []
    human_judgment: true
    rationale: "Observed in the user's signed-in Chrome session; a browser and a Google login cannot be replayed by automation"

duration: ~60min
completed: 2026-11-15
status: complete
---

# Phase 4 Plan 15: Guarda offset diagnosis Summary

**Offline test proves the scene offset travels index -> MCP -> bot -> Chat card as `#t=<seconds>`, a live Chrome run shows every hop keeps the fragment, and the decision is no-fix because the 04-13 click was a fallback row.**

## Performance

- **Duration:** ~60 min (offline tracer, live run by the orchestrator, record)
- **Completed:** 2026-11-15
- **Tasks:** 3
- **Files modified:** 1 (one new test file; no production change)

## Accomplishments

- `tests/unit/chat_bot/test_guarda_offset_path.py` drives one Guides section with a 125 s scene offset through the real MCP `guides_search` tool, the bot MCP client, the answer workflow and the Chat card renderer, and asserts the Guarda button URL ends with `#t=125`. A second test pins that a `readme_fallback` row gives the bare object URL. A third test pins that the converted card keeps the fragment.
- Our code keeps the offset: the three tests passed on first run, so no production file changed.
- Mutation check: dropping the fragment in `video_link` made the scene and conversion tests fail; reverted.
- Live diagnosis on one scene-mapped section, all hops keep the offset (below).

## Task Commits

1. **Task 1: Tracer, scene offset from index to Guarda button, offline** - `6dba386` (test)
2. **Task 2: Live diagnosis** - no code; observations recorded below (probe container stopped, `.cache/guarda-probe` removed, `docker ps --filter name=guarda-probe -q` prints nothing)
3. **Task 3: Decision** - recorded below; `04-CONTEXT.md` unchanged (D-16 stays as written)

**Plan metadata:** the docs commit that carries this file (docs: complete plan)

## Live diagnosis

Section: guide `AI-Engineering/LangChain/LANGSMITH_GUIDE.md`, `6. Feedback > The user-feedback loop, wired properly`, video object `videos/langsmith.mp4`, offset 202 s (index start_seconds 202.525, source scene). Question asked in Chat: "How do I wire the user-feedback loop in LangSmith?"; the answer card cited this section with a Guarda button. Run by the orchestrator in the user's signed-in Chrome session on 2026-11-15. Hosts named only.

- P0: yes (inferred) - Chat web renders the Guarda button as a JS button with no href in the DOM, so "copy link address" is not available; the URL Chat opened on click ended with #t=202.
- P1: yes, yes - direct open of the storage.cloud.google.com URL with #t=202 redirected to a *-apidata.googleusercontent.com host; the address bar kept #t=202 and playback started at the offset (currentTime about 209 s a few seconds after load).
- P2: yes, yes - clicking Guarda opened a new tab on a *-apidata.googleusercontent.com host with #t=202; playback at about 214 s a few seconds after load.
- P3: yes, yes - the localhost probe page played the video with the user's Google session; currentTime about 205 s.

Reading: the fragment survives every hop (Chat link, storage redirect, click, embedded page). Our own code keeps it (Task 1). The 04-13 check-10 failure was most likely a fallback row with no offset, clicked before 04-14 raised scene coverage from 238 to 708 rows. This also settles flagged assumption RESEARCH A7: a URL fragment survives the storage.cloud.google.com redirect chain.

Side observation (not part of this plan): Chat first showed "AI Buddy non risponde" before the "Sto cercando nelle fonti..." placeholder and the answer arrived. This is the known cold-start versus Chat deadline interaction; noted only.

## Guarda decision

decision: no-fix

Chosen by the owner: "No fix: the 04-13 click was a fallback row". Justified by P0 to P2 all showing the offset on the scene-mapped section, plus Task 1 finding no loss in our own code. 04-16 only re-runs live check 10 on a scene-mapped section; no code change or deploy. D-16 stays as written in 04-CONTEXT.md, so no interpretation line was appended.

## TDD Gate Compliance

Task 1 is a characterization test of existing behaviour (tdd="true", type tracer). The three tests passed on the first run, so there was no failing RED state to commit and no separate `test` then `feat` commit pair; one `test(04-15)` commit carries the test. A mutation check stood in for the RED evidence: removing the fragment from `video_link` made the scene-offset and conversion tests fail, then the change was reverted. No GREEN production commit exists because no production code changed.

## Files Created/Modified

- `tests/unit/chat_bot/test_guarda_offset_path.py` - end-to-end offline proof of the `#t=` path, scene and fallback rows, and card conversion

## Decisions Made

- no-fix (see Guarda decision). The only live evidence that pointed at a lost offset was a click on a row that could not have had one.

## Deviations from Plan

- Task 1 committed on `main` although `git.base-branch` reports main as protected; this follows the project rule "work on main, no branches". Not a code deviation.
- Task 2 live steps were run by the orchestrator in Chrome (the plan's allowed route "Claude, run it in Chrome"). P0 is "yes (inferred)": Chat web exposes no href to copy, so the fragment was read from the URL Chat opened on click.

**Total deviations:** 0 auto-fixed. **Impact on plan:** none.

## Issues Encountered

- Chat web renders Guarda as a JS button, so the plan's "copy link address" step could not run literally; replaced by reading the URL opened on click (same evidence as P2).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 04-16 only needs to re-run live check 10 on a scene-mapped section (for example the langsmith section above) and record the result.
- No new public route, no deploy, no D-16 change.

## Known Stubs

None.

## Self-Check: PASSED

- `tests/unit/chat_bot/test_guarda_offset_path.py` exists; commit `6dba386` is an ancestor of HEAD.
- Probe stopped, `.cache/guarda-probe` removed.

---
*Phase: 04-infrastructure-and-ci-cd*
*Completed: 2026-11-15*
