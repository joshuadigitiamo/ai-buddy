---
phase: 04-infrastructure-and-ci-cd
plan: 16
subsystem: chat-bot
tags: [guarda, video-offset, live-check, gap-closure, sc5]
status: complete

requires:
  - phase: 04-infrastructure-and-ci-cd
    provides: 04-15 decision no-fix (the scene offset survives every hop)
provides:
  - "Live check 10 re-run: Guarda opens the private video inline at the section offset"
affects: [ROADMAP SC5, WINDOWS 7]

requirements-completed: [INFRA-04]

duration: 2026-11-16
completed: 2026-11-16
---

# Phase 4 Plan 16: Guarda live re-check Summary

**Decision no-fix (04-15): no code change and no deploy. Live check 10 passed on 2026-11-16: Guarda opened the Guides video inline and playback started at the section offset.**

## Tasks

- Task 1: not applicable (decision no-fix).
- Task 2: not applicable (decision no-fix).
- Task 3: no deploy (no-fix); live check 10 run by Claude in the owner's Chrome session at his request.

## Live check 10

Guide file `langsmith.mp4` (LANGSMITH_GUIDE), section "6. Feedback > The user-feedback loop, wired properly", offset 202 s. Run on the chat-bot revision deployed from `cf7e7c3`.

1. Question citing the section: yes. "How do I wire the user-feedback loop in LangSmith?" returned a card listing that section with a Guarda button.
2. Guarda opens inline at the offset: yes. The button opened a browser tab on the Cloud Storage download host with `#t=202`; the page holds a playing `<video>` element (not a download), at 211 s about 9 s after the click, duration 843 s; the frame shows the "Feedback" slide.
3. `/guarda` route returns 404: n/a (no-fix).
4. Player CSP and no-referrer headers: n/a (no-fix).

## Notes

- The first message after idle still shows "AI Buddy non risponde" in Chat while the answer arrives in the thread; this is the cold-start limit recorded under 04-26 `## Gaps`, not a Guarda issue.
- Playback needs the viewer's own read access to the videos bucket (the owner keeps `roles/storage.objectViewer` there after 04-26 removed `objectAdmin`).

## Gaps

None.
