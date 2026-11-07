---
phase: 03-google-chat-bot
plan: 08
subsystem: bot-rendering
tags: [google-chat, cardsv2, rendering, sanitising, tdd]

requires:
  - phase: 03-google-chat-bot (03-01)
    provides: "bot09_rendering decision (handbook text citation, VIDEO_THUMBNAIL_URL required HTTPS setting)"
  - phase: 03-google-chat-bot (03-03)
    provides: "render.RenderedMessage, render_reply tracer, schemas.BotReply/Evidence/Referente, run_workflow, FakeLlm and connector fixtures"
  - phase: 03-google-chat-bot (03-05)
    provides: "BotReply.referente on kind answer for sensitive topics; Referente.contact_source"
provides:
  - "render.render_reply: Chat text and cardsV2 for every BotReply kind"
  - "render.sanitize_prose, MAX_ANSWER_CHARS=3500, MAX_MESSAGE_CHARS=4000, MAX_VIDEO_SECTIONS=3, VIDEO_CARD_ID, VIDEO_CARD_TITLE"
  - "tests/unit/chat_bot/test_render.py: 13 tests (card tracer plus 12 behavior tests)"
affects: [03-09, 03-10, 03-11, 03-12]

actuals:
  tokens: 3816
  tasks: 2
  commits: 3
plan_head_before: 29546b56e9787b8be7181df7421cca35c5d32612
commits: 3
plan_head_after: 2cc6aa46ded3fc878bf9a9af3deb72297c12aa90

tech-stack:
  added: []
  patterns:
    - "Renderer emits Chat REST JSON (cardsV2); GAPIC conversion stays in the Chat API adapter (03-10)"
    - "Every link, button and contact is built from Evidence/Referente; model prose passes through sanitize_prose"
    - "Message fitting by dropping whole trailing Fonte lines, with a last-resort clamp"

key-files:
  created:
    - tests/unit/chat_bot/test_render.py
  modified:
    - services/chat_bot/buddy_bot/render.py

key-decisions:
  - "A card section exists only for a cited Guides source whose video_url starts with http:// or https://; a non-web scheme gets no section at all, so no Guarda button can point to it (T-03-23). A source with an ftp video still gets its text Fonte line"
  - "Order inside a sensitive answer: prose, Fonte lines, `Contatto dal manuale: <title> (<url>)`, then the fixed sentence `Per il tuo caso specifico chiedi a <referente>.` as the last line"
  - "Refusal and referral: sentence first, provenance line second on its own line (the sentence stays the message prefix, as 03-05 tests expect)"
  - "A final clamp (text[:3999] + ellipsis) keeps every kind within 4,000 characters even if a contact copied from the handbook is huge; whole Fonte lines are still dropped first"

patterns-established:
  - "Deduplicate sources by source_url keeping first appearance before building both Fonte lines and card sections"

requirements-completed: [BOT-09, BOT-05, BOT-10]

coverage:
  - id: D1
    description: "A Guides answer with a mapped video renders text plus a cardsV2 card: thumbnail image, Indicizzata line, Fonte button (permalink) and Guarda button (video URL with #t=12)"
    requirement: BOT-09
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_render.py#test_guides_answer_with_mapped_video_renders_card_with_fonte_and_guarda"
        status: pass
    human_judgment: false
  - id: D2
    description: "Handbook-only answers cite as text `Fonte: Manuale – <title> (handbook://<id>), revisione <date>` with no card; Guides sources without video stay text-only"
    requirement: BOT-09
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_render.py#test_handbook_only_answer_cites_as_text_and_has_no_card"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_render.py#test_guides_source_without_video_has_a_fonte_line_and_no_card"
        status: pass
    human_judgment: false
  - id: D3
    description: "Refusal, referral, smalltalk and error never carry a card; refusal, referral and sensitive answers name the handbook page the contact came from; sensitive answers end with the fixed referral sentence"
    requirement: BOT-05
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_render.py#test_no_reply_kind_other_than_answer_carries_a_card"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_render.py#test_refusal_with_handbook_contact_names_the_page_the_contact_came_from"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_render.py#test_sensitive_answer_ends_with_the_referral_sentence_after_the_fonte_lines"
        status: pass
    human_judgment: false
  - id: D4
    description: "http(s):// and handbook:// tokens and angle brackets in model prose are removed or neutralised, so every link comes from this run's Evidence"
    requirement: BOT-05
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_render.py#test_model_links_and_chat_markup_are_removed_from_the_prose"
        status: pass
    human_judgment: false
  - id: D5
    description: "Sources keep first-citation order, each once; prose capped at 3,500 characters with an ellipsis; whole message never above 4,000 characters"
    requirement: BOT-10
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_render.py#test_sources_keep_first_citation_order_and_each_appears_once"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_render.py#test_long_prose_is_capped_and_the_whole_message_stays_within_the_limit"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_render.py#test_oversized_contact_still_leaves_a_message_within_the_limit"
        status: pass
    human_judgment: false
  - id: D6
    description: "A card holds at most three video sections; no image widget or empty imageUrl without a thumbnail; a non-http video_url gets no button"
    requirement: BOT-09
    verification:
      - kind: unit
        ref: "tests/unit/chat_bot/test_render.py#test_a_card_holds_at_most_three_video_sections_in_citation_order"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_render.py#test_without_a_thumbnail_the_card_has_no_image_widget"
        status: pass
      - kind: unit
        ref: "tests/unit/chat_bot/test_render.py#test_a_video_url_that_is_not_http_gets_no_guarda_button"
        status: pass
    human_judgment: false
  - id: D7
    description: "How the card and the thumbnail look in a real Google Chat client, and that Chat accepts the REST card shape after the 03-10 GAPIC conversion"
    verification: []
    human_judgment: true
    rationale: "Visual result and Chat's acceptance of the card are only observable live; covered by the 03-12 live checkpoint (the thumbnail value is supplied there)"

duration: 12min
completed: 2026-11-07
status: complete
---

# Phase 3 Plan 08: Chat Rendering Summary

**`render_reply` now produces the full Chat message for every reply kind: bot-built Fonte lines in first-citation order, a cardsV2 video card (static thumbnail, "Fonte" and "Guarda" buttons, at most three sections) for cited Guides sections with a mapped video, sanitised model prose, the sensitive-answer referral sentence, and hard length caps.**

## Performance

- **Duration:** about 12 min (start time was not captured; derived from the first task commit)
- **Completed:** 2026-11-07
- **Tasks:** 2 (1 tracer, 1 TDD)
- **Files:** 2 (1 created, 1 modified)

## Accomplishments

- Tracer: run_workflow over the real in-memory `buddy_mcp` server with a scripted LLM, citing the MAPPED Guides permalink, renders one card whose section holds the image (the supplied thumbnail URL), the "Indicizzata il" line and a button list "Fonte" (permalink) and "Guarda" (`https://videos.example.invalid/demo.mp4#t=12`).
- Handbook answers: `Fonte: Manuale – <title> (handbook://<id>), revisione <date>` as text, no card (03-01 bot09_rendering 2a).
- D-02 output guardrail: `sanitize_prose` removes `http(s)://` and `handbook://` tokens up to the next whitespace, turns `<` and `>` into `‹` and `›` and collapses space runs; only the model answer goes through it. Titles, links and contacts come from Evidence and Referente.
- BOT-05 ordering: sources deduplicated by `source_url`, order of first citation, for both Fonte lines and card sections.
- BOT-10 caps: prose at 3,500 characters ending with an ellipsis, message at 4,000 by dropping whole trailing Fonte lines (a URL is never cut), last-resort clamp for a pathological contact.
- 03-05 handoff: kind `answer` with a `referente` ends with `Per il tuo caso specifico chiedi a <referente>.`; refusal, referral and sensitive answers add `Contatto dal manuale: <title> (<source_url>)` when `contact_source` is set.
- Full gate `./run-unit-tests.sh --all` (ruff, ruff format, mypy --strict, pytest): 803 passed, 21 skipped (emulator and local-only), coverage 97.61%.

## Task Commits

1. **Task 1: tracer, Guides answer with mapped video renders a card** - `03895a7` (feat)
2. **Task 2 RED: failing behavior tests (with scaffold)** - `caba29b` (test)
3. **Task 2 GREEN: citations, sanitising, ordering, caps, card limits** - `2cc6aa4` (feat)

Tracer feedback gate: auto mode off, `human_verify_mode` default `end-of-phase`, the tracer's `<verify>` is automated-only, so `--all` was re-run end to end after the tracer was green (791 passed) before expansion.

No REFACTOR commit: the GREEN implementation needed no cleanup.

## TDD Gate Compliance

- **RED** (`caba29b`): of 11 new behavior tests, 8 failed on their planned assertions (missing contact provenance line, missing trailing referral sentence, `<` left in prose, duplicate source line, prose 5,000 instead of 3,500 characters, message 5,026 instead of 4,000 characters, 5 card sections instead of 3, a card built for a non-http video). 3 tests (handbook-only text, Guides without video, no image without thumbnail) were already satisfied by the 03-03 renderer and the tracer and passed at RED; they pin behavior, they are not RED targets. Semantic assessment: each failing target executed and failed on the planned assertion.
- The first RED run was an `ImportError` (the tests import `MAX_*` and `sanitize_prose`, which did not exist). That is not RED evidence, so the RED commit carries a minimal scaffold in `render.py` (the three constants and an identity `sanitize_prose`); RED evidence is the run on the scaffolded tree.
- Machine check `gsd_run check tdd-red-evidence` was not run: its supported report formats are TAP, JUnit XML, swift-testing, unittest and go test, and this project's runner is pytest console output. RED evidence is the console assertions above, assessed by hand.
- Order check: `test(03-08)` precedes `feat(03-08)` and the final `feat` descends from it.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Lint failures in the RED test file**
- **Found during:** Task 2 GREEN, first `--all` run
- **Issue:** test_render.py had an unsorted import and two E501 lines (the RED commit was made before the full lint gate ran)
- **Fix:** sorted the import, split the two long lines
- **Files modified:** tests/unit/chat_bot/test_render.py
- **Commit:** `2cc6aa4`

**Interpretation notes (not deviations):**
- The plan says a `video_url` that is not http(s) gets no Guarda button "for that section". Implemented as no section at all for such a source, which satisfies the stated truth and T-03-23 and avoids a card with only a "Fonte" button.
- The plan's refusal example reads "plus a line naming Contatti (handbook://05-contatti)"; the line is `Contatto dal manuale: Contatti (handbook://05-contatti)`, the format given in the Task 2 action.

**Total deviations:** 1 auto-fixed (1 lint). **Impact:** none on behavior.

## Issues Encountered

None.

## Known Stubs

None. `video_thumbnail_url=None` omits the image widget by design (the setting itself is required at startup by `BotSettings`, 03-06). The real thumbnail value is an open item for Joshua at 03-12; tests use the synthetic `https://example.invalid/thumb.png`.

## Threat Flags

None. T-03-22 (model-written links and Chat markup) and T-03-23 (non-web scheme buttons) are mitigated and tested; no new endpoint, auth path or file access.

## User Setup Required

None in this plan. Carried to 03-12: Joshua supplies `VIDEO_THUMBNAIL_URL` through `.env`.

## Next Phase Readiness

- 03-09 and 03-10 can pass `RenderedMessage.text` and `cards_v2` straight to `ChatApi.update_message`; the cards are Chat REST JSON and 03-10 converts them to the GAPIC message.
- 03-12 live check: confirm the card renders in Chat and that the "Guarda" button opens the scene clip.

## Self-Check: PASSED

- FOUND: services/chat_bot/buddy_bot/render.py, tests/unit/chat_bot/test_render.py
- FOUND commits 03895a7, caba29b, 2cc6aa4 on HEAD (`git merge-base --is-ancestor`)
- Acceptance criteria re-run: `"Guarda"` 1, `buttonList` 1, `demo.mp4#t=12` 1 (Task 1); `def sanitize_prose` 1, `MAX_(ANSWER|MESSAGE)_CHARS` 7 (>= 4), `def test_` 13 (>= 10) (Task 2)
- Plan verification: `--single-file test_render.py tests/unit/chat_bot` 13 passed (>= 11); `--all` exit 0
