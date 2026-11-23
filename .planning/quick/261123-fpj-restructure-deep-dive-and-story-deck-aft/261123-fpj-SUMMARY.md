---
phase: quick-261123-fpj
plan: 01
status: complete
commits: 0
---

# Quick 261123-fpj Summary: restructure the deep dive and the story deck

## Earlier edits of 2026-11-23 (recorded, no rework)

- Both decks were rewritten from the plan to what was built and measured.
- Four inline SVG diagrams (architecture, cloud deployment, local kind, bot workflow) were made with the diagram-design skill and embedded only in the decks.
- The owner's name was removed from both decks.
- Exact gate results were replaced by general wording, at the user's request.
- Four reviewers (clear writing, technical reader, management reader, fact check) reviewed the decks read-only. They ran as plain agents, not through GSD, per the user's rule.

## Process notes

- The decks are gitignored, so no deck file is committed. The orchestrator commits PLAN, SUMMARY and the gate script after approval; this run made no commit and did not touch STATE.md or `.planning/config.json` (orchestrator override).
- Deviation from the plan (Rule 3, blocking): the plan splits `GATE_FORBIDDEN` on commas, but several forbidden literals contain a comma (decimal numbers). Split on commas, they would become short fragments that match almost any text. The gate script splits on newlines instead, and the gitignored list file holds one entry per line. Nothing else in the contract changed.
- Deviation (Rule 1): `Path.read_text(newline=...)` exists only from Python 3.13; the gate image is 3.12, so the script reads bytes and decodes them.
- User decision recorded during the run: the subscription the developer uses is a personal Claude Max subscription. Both decks use the wording "un abbonamento Claude Max personale" and contain no statement that the account is Team or that the Team-versus-Max question is open. The Team seats in the cost table stay: they are the licence proposal for colleagues, a separate topic. This replaces the plan's earlier instruction to keep the "Max o Team" wording.
- The T1 check "T1 commit holds one file" does not apply: no commit was made.

## T1

Gate script written (stdlib, Python 3.12, no forbidden literal inside). Backups of both decks taken and compared byte for byte. Forbidden list created (gitignored). Deep dive restructured with a throwaway script: 23 sections in three parts (ids a1, a2, a6, a7, b1..b12, c1..c7), TOC in three groups, numeric cross-references rewritten to the new codes, SVG markup untouched.

Mutation checks: a literal present in both decks makes `forbidden-strings` FAIL on both files without echoing the literal; one `</svg>` removed makes `svg-count` FAIL.

Gate, before the restructure (OK/FAIL lines of the structural checks):

- OK on both files: forbidden-strings, clickup-ids, svg-count, svg-geometry, unique-ids, anchors, section-balance.
- FAIL: bot-terms (both files), parts, old-codes-a, old-codes-b (deep dive).

Gate, after the restructure:

- OK on the deep dive: forbidden-strings, clickup-ids, svg-count, svg-geometry, unique-ids, anchors, section-balance, parts.
- FAIL: bot-terms (both files), old-codes-a, old-codes-b (deep dive).

## T2

Deep dive, parts owned by T2:

- Header: shorter lede that names the three parts; "In breve" box after the header (what it is, does it work, who uses it, what is missing).
- Parte A: sections A1 (problem, shortened, plain language) and A2 (what was built, measured; general results; the four approved changes before the last measurement; five-phase table without plan counts or test and coverage counts) rewritten; three new sections A3 (decisions table, licences first), A4 (one costs table, today versus rollout, total range, unknowns named), A5 (ranked risks, each with who handles it); A6 (numbered next steps, no ordering claim, "after the pilot" and "out of scope" lists) and A7 (questions, counts match A6: seven items). The external-dependencies table was merged into A3.
- Choice for A2: the end-to-end example stays only in Parte B (B8); A2 has no short version.
- Parte C: marked as September research; old internal codes removed or said in words; terminology and calques fixed (masking, limite di frequenza, Impegno, UE, sorveglianza strisciante, and similar); the GPU and model-serving glossary (vLLM, MoE, VRAM, FP8/Q4, cold start) added to C6; C5 now says the September plan cached the whole handbook while the built bot searches; C4 says the developer's Max account differs from the shared Max accounts.
- Footer: sources in general terms only.
- SPEC section 3 item numbers applied in T2 text: 2 (partly), 8, 10, 11, 12 (A5 only), 13, 14, 15 (as replaced by the user decision above), 16 (contradictions in C4, C5 and A7).

Gate after T2, deep dive: OK forbidden-strings, clickup-ids, svg-count, svg-geometry, unique-ids, anchors, section-balance, parts, old-codes-a; FAIL bot-terms and old-codes-b (T3 owns Parte B).

## T3

Deep dive, Parte B:

- B1: glossary rebuilt for the terms Parte B uses (gate of the Milestone, golden set, Recall@5, MCP, tool, custom connector, Skill, RAG, LangGraph, BM25/FTS5, embedding and RRF, gap log, hand-over to a person, OAuth, JWT and ID token, Cloud Run, kind and sidecar, Meridian, Vertex and Bedrock, seat, cold start, "live"); the GPU and model-serving terms live in C6.
- B2 to B12: terminology and facts corrected in place (bot check named "controllo delle citazioni" everywhere, including headings and the numbered bot steps; "gate" only for the Milestone gate); numbered lists for the six checks, the bot steps, the CI steps and the four approved changes; failure paths added (vulnerability found in CI, candidate checks failing, the 120-second limit); old internal codes and the "retrieval" wording removed; B5 renamed to "Ricerca"; B12 heading renamed to "Cosa è verificato e cosa no" and its closing box to "In sintesi"; acronyms spelled out at first use in Parte B.
- Answers judged wrong in the eval were described by cause, without counts, so the text does not reveal results.
- SVG labels changed (text only): in the architecture diagram the bot box label and the sync-job label; in the bot workflow diagram the decision label ("Controllo"), the six-checks annotation and the confidence wording, plus the `<desc>` sentence; legend entry "Servizio nostro" became "Servizio del progetto" in all three diagrams that have it. Every changed label stays shorter than its box.
- Story deck: slides 1 to 3, 6, 7, 11 to 14 changed. Slide 3 (four read-only tools plus the gap log tool), slide 6 (bot check named), slide 7 (wrong answers described by cause), slide 11 (costs aligned with A4, Meridian and subscription wording), slide 12 (bot check named, "Passa a una persona"), slide 13 (no ordering claim: title, plus signs instead of arrows; model sub-label "Console Anthropic (Vertex da sviluppare)"; reminder days 1, 7, 30, 60, 90), slide 14 (budget wording with the Vertex fact, 15 seats, title without a count). Same 14 slides, same order; slide 7 keeps the Milestone gate wording.
- SPEC section 3 item numbers applied in T3 text: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13 (Parte C, T2), 14, 16.
- Final small fixes: "per digest" became "identificate dal digest" and "app Google Chat" became "bot Google Chat" in the remaining places.

## Spec items kept, dropped or not applied (generic)

- Kept: slide 7 "il gate è passato" (Milestone gate); the "2 seats = 50 $" figure, now framed as the example of one shared Max replaced by two seats; the golden-set composition table (it is not a gate result).
- Dropped: the short end-to-end example in A2 (it stays in B8 only); adding "(più docker compose)" to slide 10 (not needed); renaming the "Nuove keyword" label in the workflow diagram and extending the "hostPath" legend entry (a longer label would not fit its box; the caption now says it is one of two exceptions); the plan's "Max o Team" wording (replaced by the user decision above).
- Not applied exhaustively: the spec's clear-writing pass was applied in full to the new and rewritten parts (header, A1 to A7, B1, bot steps, correction box, wrong-answer box), and by targeted edits to the rest of Parte B, Parte C and the story deck. Long table cells in Parte C keep their original sentences where no spec item applied.
- Gate script: forbidden literals are split on newlines, not commas (some literals contain a comma).

BK (`docs/internal/presentation/backup-261123/`) keeps the pre-task copies of both decks until the user has reviewed them. The throwaway scripts and text files used for the edits are in the same gitignored folder.

## Gate

Final gate output (both decks):

```
OK forbidden-strings deep-dive.html -- 9 entries, no hit
OK clickup-ids deep-dive.html -- 0 match(es)
OK svg-count deep-dive.html -- 4 open, 4 close
OK svg-geometry deep-dive.html -- 4 svg identical to backup
OK unique-ids deep-dive.html -- 49 ids unique
OK anchors deep-dive.html -- 29 links ok
OK section-balance deep-dive.html -- 26 open, 26 close
OK bot-terms deep-dive.html -- 0 bot-gate phrase(s), 0 'gate' in the bot section
OK parts deep-dive.html -- three parts in order
OK old-codes-a deep-dive.html -- none
OK old-codes-b deep-dive.html -- none
OK forbidden-strings story-deck.html -- 9 entries, no hit
OK clickup-ids story-deck.html -- 0 match(es)
OK svg-count story-deck.html -- 4 open, 4 close
OK svg-geometry story-deck.html -- 4 svg identical to backup
OK unique-ids story-deck.html -- 23 ids unique
OK anchors story-deck.html -- 0 links ok
OK section-balance story-deck.html -- 0 open, 0 close
OK bot-terms story-deck.html -- 0 bot-gate phrase(s), 0 'gate' in the bot section
RESULT: PASS
```
