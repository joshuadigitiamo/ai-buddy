---
status: complete
phase: 02-mcp-server-and-skill
source: 02-01-SUMMARY.md, 02-02-SUMMARY.md, 02-03-SUMMARY.md, 02-04-SUMMARY.md, 02-05-SUMMARY.md, 02-06-SUMMARY.md, 02-07-SUMMARY.md
started: 2026-11-06T22:17:51Z
updated: 2026-11-06T22:37:10.339Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Server built from ai-buddy-test starts with AUTH_MODE=off and a published index.db, no traceback. initialize returns 200 without mcp-session-id, GET /mcp returns 405, tools/list shows the 5 tools (handbook_search, handbook_get, guides_search, guides_get_section, buddy_report_gap).
result: pass
verified_by: claude (live HTTP on 127.0.0.1:18000; port 8000 held by another project)
note: first boot refused with one ERROR line because .env lacked GUIDES_WEB_BASE and GOOGLE_CLOUD_PROJECT (local config, not code); keys added, boot clean.

### 2. Italian Handbook Search
expected: handbook_search "quando posso chiedere una feria?" returns status ok, first result page 17-ferie-e-permessi with full markdown text, source_url handbook://17-ferie-e-permessi, revision_date 2026-07-29, revision_kind last_updated.
result: pass
verified_by: claude (live server, real handbook snapshot)

### 3. Accent Folding and No Results
expected: handbook_search "festività", "FESTIVITÀ" and "festivita" all return 17-ferie-e-permessi first. handbook_search "xyzzy" returns status no_results, isError false, text "Nessun risultato per: xyzzy".
result: pass
verified_by: claude (live server)

### 4. Handbook TOC and Page Resource
expected: handbook_get with no section returns the table of contents (22 pages, position order, starting 00-handbook-digitiamo). Reading handbook://17-ferie-e-permessi starts with "Fonte: handbook://17-ferie-e-permessi - Revisione: 2026-07-29", blank line, "# Ferie e Permessi". handbook_get section "nope" is no_results (isError false); resource handbook://nope is an MCP error "Pagina non trovata: nope".
result: pass
verified_by: claude (live server)

### 5. Gap Report Written to Firestore
expected: With the server pointed at the Firestore emulator (or `./run-unit-tests.sh --emulator`), buddy_report_gap("domanda senza risposta") returns status recorded, a gap_id and marker "nessuna fonte trovata". The stored doc has exactly question, marker, created_at, expire_at (+90 days), build_id, tried, and no user identity.
result: pass
verified_by: claude (./run-unit-tests.sh --emulator: 4 passed, incl. test_record_writes_one_gap_document and test_real_process_serves_five_tools_and_records_a_gap)

### 6. Skill Package and Install Guide
expected: `cd skills && zip -r digitiamo-buddy.zip digitiamo-buddy` produces a zip claude.ai accepts in Customize > Skills (or copy to ~/.claude/skills/ and Claude Code lists digitiamo-buddy). docs/install-guide.md reads as one page covering claude.ai, Claude Desktop and Claude Code.
result: pass
verified_by: claude (zip uploaded to claude.ai Customize > Skills via Chrome MCP, personal Skill v1 in Digitiamo org, not published to org; copied to ~/.claude/skills and listed by Claude Code; description 172 chars; install guide 38 lines / 276 words)

### 7. Skill Behaviour with Live Model
expected: With connector + Skill active, "come si richiedono le ferie?" gets the Italian template (Risposta / Fonte / Data di revisione), handbook first, one citation per source. An unanswerable question gets "Non lo so, chiedi a ..." plus exactly one buddy_report_gap call. A sensitive question (stipendio, salute) gets only the general rule plus an HR referral by role.
result: pass
verified_by: claude (3 headless Claude Code sessions, Skill + local server on :18000; ferie: handbook-first, single citation; unknown: one buddy_report_gap + 'Non lo so, chiedi a HR'; malattia: general rule + HR referral, Italian template)
note: answer a came out in English; attributed to the session's always-English rule, not the Skill. Gap writes returned 'gap log unavailable' because the container had no Google credentials (emulator path verified in test 5).

### 8. Live Google Login with @digitiamo.com
expected: With AUTH_MODE=on behind a public HTTPS URL, connecting from Claude Code /mcp runs the Google consent flow (DCR, Internal consent screen), login with an @digitiamo.com account succeeds, and the 5 tools are listed.
result: pass
note: confirmed by user; live OAuth run recorded earlier in 02-VERIFICATION.md (DCR, consent, Google Internal login, token, 5 tools)

### 9. External Google Account Rejected (live)
expected: Logging in through the live OAuth flow with a non-@digitiamo.com Google account is rejected; no tool call succeeds.
result: pass
note: passed by user decision without a live run; the OAuth consent screen is Internal, so Google blocks non-org accounts before the server; the server-side domain check is covered by automated test 18 (02-05 D2). Live external-account run still worth doing in Phase 4.

### 10. claude.ai Custom Connector
expected: An org owner adds the server as a custom connector in claude.ai; Google authorization completes, the 5 tools are listed, and a handbook question gets an answer with Fonte and Data di revisione.
result: skipped
reason: "Deferred follow-up: I don't think we can contact the org owner on this matter" (also needs Phase 4 hosted URL; a member-level personal custom connector may avoid the org owner)

### 11. Stateless JSON streamable-HTTP transport
expected: Stateless JSON streamable-HTTP transport: initialize 200 JSON without mcp-session-id, GET /mcp 405
result: pass
source: automated
coverage_id: 02-01/D1

### 12. guides_search cited and video-linked
expected: guides_search over HTTP returns cited, video-linked sections pinned to the indexed commit
result: pass
source: automated
coverage_id: 02-01/D2

### 13. guides_get_section by id
expected: guides_get_section by section_id; unknown id is no_results; single-line anchor and percent-encoded permalink
result: pass
source: automated
coverage_id: 02-01/D3

### 14. Explicit no_results and inert FTS5 operators
expected: Explicit no_results for empty, punctuation-only and unmatched queries; FTS5 operators inert; limit clamp 1..10 default 5; stable tie order
result: pass
source: automated
coverage_id: 02-01/D4

### 15. Cold-start failures and read-only artifacts
expected: Cold-start failures (missing directory, no index, other schema major, undated page) and read-only artifact directory
result: pass
source: automated
coverage_id: 02-01/D5

### 16. D-06 output contract
expected: Full D-06 output contract for the five tools, required citation fields, GAP_MARKER
result: pass
source: automated
coverage_id: 02-01/D6

### 17. Anonymous and bad tokens rejected; bot SA token accepted
expected: Anonymous and malformed or wrongly signed callers get 401 with resource_metadata; the bot's service-account ID token reaches tools/list through MultiAuth
result: pass
source: automated
coverage_id: 02-05/D1

### 18. Exact-domain e-mail check
expected: Human path accepts only verified e-mails of exactly the allowed domain (case-insensitive), rejects subdomain, suffix and hd-mismatch cases
result: pass
source: automated
coverage_id: 02-05/D2

### 19. OAuth metadata and redirect limits
expected: OAuth metadata advertises registration, S256 and CIMD; redirects limited to claude.ai and loopback; proxy uses the store it was given; serving writes nothing to disk
result: pass
source: automated
coverage_id: 02-05/D3

### 20. Host/Origin guard, AUTH_MODE guard, rate limit
expected: Foreign Host and Origin are rejected before any tool; AUTH_MODE=off is refused when K_SERVICE is set; rate limit is per identity with burst N passing and N+1 refused
result: pass
source: automated
coverage_id: 02-05/D4

### 21. Real process end to end
expected: python -m buddy_mcp runs as a real process, stateless JSON HTTP, five tools, cited handbook_search, gap document with six D-10 keys in the emulator
result: pass
source: automated
coverage_id: 02-07/D1

### 22. Gap document from real server process
expected: buddy_report_gap writes the gap document end to end from a real server process
result: pass
source: automated
coverage_id: 02-07/D2

### 23. Bad configuration refused cleanly
expected: Startup refuses bad configuration with one ERROR line, no traceback, no secret values
result: pass
source: automated
coverage_id: 02-07/D3

### 24. mcp_server image runs as uid 10001
expected: mcp_server image builds and runs as uid 10001
result: pass
source: automated
coverage_id: 02-07/D4

### 25. .env.example and README
expected: .env.example holds only non-secret contract keys; README documents every server variable and the auth setup
result: pass
source: automated
coverage_id: 02-07/D5

## Summary

total: 25
passed: 24
issues: 0
pending: 0
skipped: 1
blocked: 0

## Gaps

[none]

## Deferred Follow-Ups

- test: 10
  idea: "I don't think we can contact the org owner on this matter" (claude.ai connector live check; retry in Phase 4 with hosted URL, try member-level personal connector)
  deferred_at: 2026-11-07
