---
phase: quick-261123-k6x
plan: 01
status: complete
commits: 0
---

# Quick 261123-k6x: remove planning-process references from the internal decks

The executor made no commit and staged nothing. The decks are gitignored and live only in the working tree; `docs/internal/base-k6x/` holds the pre-task copies until the decks are reviewed.

## Decisions

- TERMS-1 (plan gate): called "test di accettazione", with "sul golden set" at first use in each part. The word "gate" survives only inside `<code>` spans naming the eval job command and inside the frozen HTML comments of the SVG blocks.
- TERMS-2 (former phases): "passi di lavoro".
- TERMS-3 (Milestone): replaced by the state date ("Stato al 23/11/2026") or dropped. No new version label.
- TERMS-4 (September-plan phase numbers): the work is named instead.
- TERMS-5 (phase attributions): the fact is stated without the phase.
- TERMS-6 ("il piano"): kept where it names the project plan document.
- TERMS-7 (work-method paragraph): dropped.
- TERMS-8 (sources): plan document, September research, component documentation, code. The phase-minutes source and the planning path are dropped.
- SVG `<title>` text nodes: "AI Buddy, architettura attuale" and "AI Buddy, deployment attuale", the same wording in both decks. SVG markup and comments are untouched.

## T1

Gate script written (stdlib, reuses all fpj checks, adds planning-terms, svg-vs-base, code-spans, structure, numbers). It holds no forbidden literal and no deck text.

Gate before the story deck edit: 27 OK, 2 FAIL (planning-terms on both decks), as the plan expected (deep dive: phase x15, milestone x30, gsd x1, gate x32; story deck: gate x3, milestone x3, phase x1, planning-path x1).

Gate after the story deck edit: 28 OK, 1 FAIL (planning-terms on the deep dive). The story deck passes all 13 checks.

Mutations (all behave as expected):
- a lost date, a code span pointing to a missing file and a changed SVG label each FAIL `numbers`, `code-spans` and `svg-vs-base`;
- a phase number in prose FAILs `planning-terms`; the CLI word inside a code span does not.

| Deck | Where | Group | Occurrences | Action | Reason |
|------|-------|-------|-------------|--------|--------|
| Story | CSS header comment | sources list naming the plan document and the planning folder | 1 | rewritten | planning path dropped; sources now name the plan document, the September research, component documentation and code (TERMS-8) |
| Story | slide 01 kicker | milestone label next to the state date | 1 | rewritten | label dropped, state date kept; no stat added (TERMS-3) |
| Story | slide 03 body | "five phases" with their close dates | 1 | rewritten | now "five work steps", dates and list unchanged (TERMS-2) |
| Story | slide 04 and slide 08 SVG `<title>` | milestone in the diagram title | 2 | rewritten | text node only, same wording in both decks |
| Story | slide 07 headline | plan gate passed | 1 | rewritten | "test di accettazione sul golden set è superato" (TERMS-1); thresholds in the table unchanged |
| Story | slide 11, limit 3 and 4 | plan gate uses the current handbook copy | 1 | rewritten | term replaced (TERMS-1) |
| Story | slide 13, step 3 | new gate run on the HR golden set | 1 | rewritten | term replaced (TERMS-1) |
| Story | SVG blocks (decision node, check annotation) | HTML comments naming the gate | 2 | kept | invisible, frozen with the SVG markup |
| Story | whole deck | CLI word inside a `<code>` span | 0 | n/a | the story deck has no such span; the kept-CLI-span case occurs only in the deep dive |

## T2

Region: deep dive head, header, "In breve", Parte A, Parte C, footer. Slice check (planning-terms on head + Parte A + Parte C + footer): OK. Full gate after T2: 28 OK, 1 FAIL (planning-terms on the deep dive, Parte B only: gate x12, milestone x14, phase x5).

| Deck | Where | Group | Occurrences | Action | Reason |
|------|-------|-------|-------------|--------|--------|
| Deep dive | meta description | milestone in the description of the document | 1 | dropped | sentence reads without it |
| Deep dive | eyebrow | milestone label plus "gate superato" | 1 | rewritten | "test di accettazione superato" (TERMS-1, TERMS-3) |
| Deep dive | "In breve", does it work | milestone, plan gate, pass date | 1 | rewritten | "test di accettazione sul golden set", date kept |
| Deep dive | A1, handbook-first principle | milestone works on the current handbook copy | 1 | rewritten | "Oggi AI Buddy lavora su ..." (TERMS-3) |
| Deep dive | A1, context box | five phases of the milestone finished | 1 | rewritten | "lavoro in cinque passi" (TERMS-2, TERMS-3) |
| Deep dive | A2 intro | milestone had to answer one question | 1 | rewritten | subject is "Il progetto" (TERMS-3) |
| Deep dive | A2 measurement table | plan gate in header, verdict row and requirement sentence | 3 | rewritten | "test di accettazione", threshold and "superato" kept (TERMS-1) |
| Deep dive | A2 "Cosa esiste oggi", measure bullet | command of the plan gate | 1 | rewritten | "il comando che dà il verdetto"; no new code span (TERMS-1) |
| Deep dive | A2 sentence on closing dates | five phases | 1 | rewritten | "cinque passi di lavoro", dates kept (TERMS-2) |
| Deep dive | A2 step table | phase header, measurement row with gate and command | 2 | rewritten | header "Passo di lavoro"; rows keep their order numbers; measurement row names the acceptance test (TERMS-1, TERMS-2) |
| Deep dive | A2 method paragraph | planning method name, next recorded plan step, milestone audit | 3 | dropped | no product fact (TERMS-7) |
| Deep dive | A2 scope callout | plan gate (twice) | 2 | rewritten | "test di accettazione" (TERMS-1) |
| Deep dive | A3 table, golden-set row | new gate run | 1 | rewritten | "nuovo run del test di accettazione" (TERMS-1) |
| Deep dive | A6 intro and golden-set step | plan gate | 2 | rewritten | TERMS-1 |
| Deep dive | A6 reminders step | plan phase number of the new-hire reminders | 1 | rewritten | "previsti dal piano" (TERMS-4) |
| Deep dive | A7 answers (works; single user; zero invented policies) | plan gate, milestone | 3 | rewritten | TERMS-1, TERMS-3; "Oggi c'è un solo utente" |
| Deep dive | C1 prose and table header | phase number of the content-cleanup work | 2 | rewritten | "la pulizia prevista dal piano" (TERMS-4) |
| Deep dive | C1 second paragraph | milestone did not wait for the cleanup | 1 | rewritten | subject is "Il progetto" (TERMS-3) |
| Deep dive | C3 table row, C7 table row | phase number of the new-hire reminders | 2 | rewritten | "previsti dal piano" (TERMS-4) |
| Deep dive | C4 heading | milestone reaches Claude through the proxy | 1 | rewritten | "Come AI Buddy raggiunge Claude" (TERMS-3) |
| Deep dive | C5 paragraph on connector order | plan gate twice, milestone | 3 | rewritten | "test di accettazione sul golden set" at first use, then short form (TERMS-1, TERMS-3) |
| Deep dive | C5 cost note | November gate run | 1 | rewritten | "il test di accettazione eseguito a novembre" (TERMS-1) |
| Deep dive | C6 model table, large row | gate passing condition | 1 | rewritten | "non supera il test di accettazione" (TERMS-1) |
| Deep dive | C6 A/B comparison | same gate as the milestone | 1 | rewritten | "lo stesso test di accettazione", thresholds as written (TERMS-1) |
| Deep dive | C7 channel paragraph | milestone built the bot on Google Chat | 1 | rewritten | "lo sviluppatore ha costruito il bot", agent already named for this fact in A2 (TERMS-5) |
| Deep dive | footer | sources: phase minutes of the milestone | 1 | rewritten | sources now: plan documents, September research, component documentation, code (TERMS-8) |

Number allowlist entries added in T2: none.

## T3

Region: deep dive Parte B and the two SVG titles. Final gate: 29 OK, RESULT: PASS.

| Deck | Where | Group | Occurrences | Action | Reason |
|------|-------|-------|-------------|--------|--------|
| Deep dive | B1 glossary, plan gate entry | term "Gate (della Milestone)" and its definition naming the milestone | 2 | rewritten | entry renamed "Test di accettazione"; position kept (the glossary is not alphabetical); the sentence that tells it apart from the bot's citation check is kept (TERMS-1) |
| Deep dive | B1 glossary, golden set entry | plan gate runs on this set | 1 | rewritten | "test di accettazione" (TERMS-1) |
| Deep dive | B1 glossary, Meridian entry | milestone uses the proxy | 1 | rewritten | "Oggi" (TERMS-3) |
| Deep dive | B2 Guides paragraph | index used by the final gate | 1 | rewritten | "l'ultimo test di accettazione" (TERMS-1) |
| Deep dive | B2 video timestamps | measure attributed to a phase of the milestone | 1 | rewritten | attribution dropped (TERMS-5); pointer added to the sync README, which documents the coverage command and its baseline |
| Deep dive | B2 open question on the Guides | milestone indexes a local checkout | 1 | rewritten | subject is "Il sync"; "domanda aperta del piano" kept (TERMS-6) |
| Deep dive | B3 manual sync | decision attributed to a phase of the milestone | 1 | rewritten | attribution dropped; pointer to the sync README, which documents the laptop sync command (TERMS-5) |
| Deep dive | B5 retrieval note | first run of the plan gate | 1 | rewritten | TERMS-1 |
| Deep dive | B6 Skill versus bot | the bot that the milestone gate measured | 1 | rewritten | TERMS-1 |
| Deep dive | B9 live proof | phase attribution of the proof with eleven checks | 1 | rewritten | attribution dropped, count kept; no pointer, because no component doc states the eleven checks (TERMS-5) |
| Deep dive | B10 eval command sentence | plan gate run by one command | 1 | rewritten | "test di accettazione"; the eval command `<code>` span is unchanged |
| Deep dive | B10 recorded-decision sentence | result of the plan gate | 1 | rewritten | TERMS-1; wording on the recorded decision kept |
| Deep dive | B10 first-run note | first run of the plan gate | 1 | rewritten | TERMS-1; thresholds untouched |
| Deep dive | B10, eval command | word naming the eval CLI command inside the `<code>` span | 1 | kept | names the CLI command inside a code span |
| Deep dive | B11 security status line | milestone status | 1 | rewritten | "Stato attuale" (TERMS-3) |
| Deep dive | B11 legal row | phase number of the content-cleanup work | 1 | rewritten | "la pulizia dei contenuti prevista dal piano" (TERMS-4) |
| Deep dive | B12 intro and verified/open table | milestone, plan gate (four rows), phase attribution of the live check | 6 | rewritten | TERMS-1, TERMS-3, TERMS-5; confidence tags kept |
| Deep dive | SVG titles (architecture, deployment) | milestone in the diagram title | 2 | rewritten | "architettura attuale", "deployment attuale"; same wording as the story deck |
| Deep dive | SVG blocks (decision node, check annotation) | HTML comments naming the gate | 2 | kept | invisible, frozen with the SVG markup |

## Open items (left as they were, for the owner)

- Two phrases mention a recorded or planned item without a phase id: "il piano non registra un ordine fra loro" (A6 intro) and "decisione registrata a settembre" (C4). They name the September plan and a September decision, not plan bookkeeping, so TERMS-6 keeps them. The gate does not flag them. Rewrite them if the owner reads them as process talk.
- The step table in A2 keeps its row numbers 1-5 as step numbers, so no number was lost.

## Number allowlist

Empty. The phase-bound strip covered every number lost with a planning reference.

## Gate

Final output, run from the repository root in Docker (file paths shortened to the file name):

```
OK forbidden-strings deep-dive.html -- 9 entries, no hit
OK clickup-ids deep-dive.html -- 0 match(es)
OK svg-count deep-dive.html -- 4 open, 4 close
OK svg-geometry deep-dive.html -- 4 svg identical to backup
OK unique-ids deep-dive.html -- 49 ids unique
OK anchors deep-dive.html -- 29 links ok
OK section-balance deep-dive.html -- 26 open, 26 close
OK bot-terms deep-dive.html -- 0 bot-gate phrase(s), 0 'gate' in the bot section
OK planning-terms deep-dive.html -- none
OK svg-vs-base deep-dive.html -- 4 svg, 2 text node(s) changed
OK code-spans deep-dive.html -- 63 spans, added: ['jobs/sync/README.md']
OK structure deep-dive.html -- 49 ids, 26 sections, 4 stages equal base
OK numbers deep-dive.html -- 180 tokens kept, 0 new
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
OK planning-terms story-deck.html -- none
OK svg-vs-base story-deck.html -- 4 svg, 2 text node(s) changed
OK code-spans story-deck.html -- 2 spans, added: []
OK structure story-deck.html -- 23 ids, 0 sections, 14 stages equal base
OK numbers story-deck.html -- 47 tokens kept, 0 new
RESULT: PASS
```

`docs/internal/base-k6x/` keeps the pre-task copies until the user reviews the decks. The executor made no commit and staged nothing.
