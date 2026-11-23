---
phase: quick-261123-ljr
plan: 01
subsystem: internal-docs
tags: [deep-dive, story-deck, guides-structure, italian, gate]
status: complete
commits: 0
requirements-completed: []
key-files:
  created:
    - .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-checks.py
  gitignored-outputs:
    - docs/internal/work-ljr/assemble.py
    - docs/internal/work-ljr/deep-dive.src.html
    - docs/internal/presentation/deep-dive.html
    - docs/internal/presentation/story-deck.html
---

# Quick 261123-ljr: deep dive rewritten to the Guides "Zero to Production" structure

Status: T1, T2 and T3 (fix pass on the round-1 review findings) done; the orchestrator's post-fix render re-check is pending. `commits: 0` is intentional: the executor stages and commits nothing, the orchestrator commits after the user's OK. BASE copies stay in place until the user reviews the files.

## Decisions

- **Final titles** (28 sections, short, double as deck kickers): 1 Cos'è AI Buddy; 2 L'architettura in un disegno; 3 Una domanda dall'inizio alla fine; 4 Le due fonti: handbook e Guides; 5 L'indice e il sync; 6 I cinque tool MCP; 7 La Skill digitiamo-buddy; 8 Il workflow del bot; 9 La ricerca per parole chiave; 10 Il controllo delle citazioni; 11 Misurare prima di dichiarare; 12 Deploy: Cloud Run, CI/CD, kind e compose; 13 Sicurezza, privacy e normativa; 14 Costi; 15 Rischi; 16 Cosa è verificato e debiti tecnici; 17 Prima di un secondo utente; 18 Licenze: un seat per persona; 19 Il modello per il rollout; 20 Il canale: Google Chat; 21 Handbook: pulizia e pagine mancanti; 22 Quando AI Buddy non è lo strumento giusto; 23 to 28 the six closing sections with the contract titles. Only section 9 differs from the outline (shorter title).
- **Structure**: header with title, subtitle, one intro paragraph for the two audiences and one line with three links (costs, risks, decision checklist); TOC grouped by level; five level dividers plus "Best practice e riferimento". The old top «In breve» box is dropped; its facts live in section 1.
- **SVG placement** (after the fix pass, by the orchestrator's ruling on the first cold-reader finding): figure 1 in section 2, figure 2 in section 8, figures 3 and 4 in section 12 under the cloud and local parts. The SVG order 1 to 4 is unchanged. Section 27 stays, as the template requires it, and is now a short overview table (sources, sync and index, MCP server, bot, user, each with a link to its section) with pointers to the figures. No check hardcoded the section of figures 3 and 4, so no CHECKS line changed; the gate still shows 37 lines.
- **CSS**: base style block copied; two allowed changes only (`nav.toc ol` without bullets and padding, new `.subtitle` rule). The unused `.snum` rule stays, as the base block is copied whole.
- **Words (visible, outside SVG)**: 6,145 in total after the fix pass (was 6,658): front matter 273, Livello 1 715, Livello 2 1,078, Livello 3 744, Livello 4 1,684, Livello 5 947, reference part 704. Within the gate range and about 45 words above the 6,100 target; Livello 4 is the largest because figures 3 and 4 with their captions now sit in section 12.
- **September research** survives only in Livello 5 (sections 18 to 22) and in the decision checklist (section 24), plus the cost figures of section 14.
- **Conventions**: 6 «In breve» boxes, 6 trade-off notes (sections 8, 9, 13, 18, 19, 22; the section 12 note was cut as a repeat of the cost note in sections 14 and 15, which leaves exactly the gate minimum), tables inside `tblwrap`, cross-references as `sezione N` links, ASCII apostrophes throughout.
- **Terms kept from the earlier rounds**: «test di accettazione», «controllo delle citazioni», «gap log», «passi di lavoro», «golden set», «test del contesto vuoto». The fix pass retires «passaggio a una persona» as a verb phrase: the bot gives the general written rule and says whom to ask («Rinvia a una persona» on the deck card). Unified terms: confidenza, istanza sempre accesa, ricerca per significato, repository, custom connector, addestramento, fascia gratuita.
- **Handbook content in general terms**: sections 10, 21 and 23 describe handbook problems by category (contradicting pages, content only in images, empty or stale pages, missing owner and date), never page-level wording.
- **Gate script**: reuses the 8 common checks of 261123-fpj and the planning-terms check of 261123-k6x, adds svg-identical, svg-markers, code-paths, old-refs, seven deep-dive checks and four deck checks. `NOT_REPO_PATHS` has two entries, neither used by the current pages: a file name that belongs to the Guides repository, and a container image name. Both are inert and kept as the plan lists them.

## Section map

| Old block | Outcome | Reason |
|-----------|---------|--------|
| Header and top «In breve» | merged into section 1 and the new header | levels replace the three-part split |
| Old TOC | cut | replaced by the level TOC |
| a1 problem, risk, context | merged into sections 1 and 10 | risk and context in 1, defences in 10 |
| a2 chain, measure table, what exists, work-step table, limits of the result | merged into sections 1, 2 and 11 | step table cut, dates kept in 1 |
| a3 eight decisions | kept in section 24 | decision checklist |
| a4 costs | kept in section 14 | scenario detail dropped |
| a5 risks | kept in section 15 | one line each |
| a6 next steps, after pilot, out of scope | merged into sections 17, 22, 9, 8, 13 | out-of-scope items became trade-off notes |
| a7 Q&A block | cut as a block | answers feed sections 1, 10, 13, 14, 18, 19 |
| b1 glossary | cut as a block | terms defined at first use or in «In breve» (6, 9, 11, 18) |
| b2 sources | merged into section 4 | area table cut |
| b3 architecture | merged into sections 2 and 5 | figure kept, Docker note shortened |
| b4 tools | kept in section 6 | |
| b5 search | kept in section 9 | |
| b6 Skill | kept in section 7 | |
| b7 bot | merged into sections 8 and 10 | check steps in 10 |
| b8 trace | kept in section 3, cases in 25 | |
| b9 infrastructure, deploy, costs | merged into sections 12, 14 and 15 | cost table condensed, accepted limits in 15 |
| b10 eval | merged into section 11 | KPI table cut, golden-set table reduced to a sentence |
| b11 security and norms | kept in section 13 | norms table 5 rows to 4 (AI literacy row cut), training box folded into 15 and 18 |
| b12 verified and open | kept in section 16 | rows merged |
| c1 quality problems | merged into section 21 | table cut, categories kept |
| c2 missing pages | merged into section 21 | priorities kept as categories |
| c3 onboarding data | merged into section 22 | statistics table and meta-analysis cut |
| c4 licences | kept in section 18 | |
| c5 backend options and costs | merged into sections 20 and 14 | comparison and scenario tables cut |
| c6 model for rollout | merged into section 19 | shortlist, VRAM, excluded models, serving, hosting table, utilisation arithmetic cut |
| c7 channel | kept in section 20 | table reduced to prose |
| Footer | merged into section 28 and the short footer | |

## New facts

- Section 28 lists the repository sources as `<code>` paths: the root and component READMEs, the deploy READMEs, the Skill file, the project plan document and the research folder. Each path exists (code-paths check); no other non-numeric fact was added.

## T1

- Baseline on the unchanged files: 28 OK, 9 FAIL (deep dive: code-paths, old-refs, toc, levels, section-numbers, word-count, title-block, conventions; deck: deck-kickers), as predicted. CHECKS needed no correction.
- After the skeleton and Livello 1: deep dive 18 OK, FAIL only word-count and conventions, as predicted.
- End of T1: all 20 deep-dive lines OK, including dd-numbers (no new number token), code-paths (80 spans) and bot-terms.
- Mutation run: a new number, a pointer to a missing file, a changed TOC link text and a skipped section number each FAIL their check (4 of 4).
- Tracer verified end to end: assembler, gate and the four SVGs.
- Hygiene: deck unchanged during T1; CHECKS holds no forbidden entry; CHECKS untracked; nothing staged.

## Slide map

| Old slide | New slide and kicker | Facts in section | Facts cut from the slide |
|-----------|----------------------|------------------|--------------------------|
| 01 title | 01, unchanged | 1 | none |
| 02 problem | 02 Livello 1 · Cos'è AI Buddy (merged with the headline of old 03) | 1 | the "answers exist but are hard to find" framing, three of the four card examples reworded to what the deep dive states |
| 03 what was built (flow) | 05 Livello 2 · I cinque tool MCP (fix pass: the flow became a table of the five tool names with one line each) | 6 | the flow, the work-step sentence; body kept as the MCP server being the single access |
| 04 architecture (SVG 1) | 03 Livello 1 · L'architettura in un disegno | 2 | none |
| 05 bot workflow (SVG 2) | 06 Livello 2 · Il workflow del bot · LangGraph | 8 | none |
| 06 example | 04 Livello 1 · Una domanda dall'inizio alla fine · testo indicativo | 3 | none |
| 07 results | 08 Livello 3 · Misurare prima di dichiarare · 22/11/2026 | 11 | the trace-registry remark; "all or nothing" wording replaced by the deep-dive wording |
| 08 cloud (SVG 3) | 09 Livello 4 · Deploy: Cloud Run, CI/CD, kind e compose · cloud | 12, 27 | none |
| 09 local (SVG 4) | 10 Livello 4 · Deploy: Cloud Run, CI/CD, kind e compose · locale | 12, 27 | none |
| 10 cloud versus local table | cut | 12 (table) | whole slide; its facts live in the section 12 table |
| 11 costs and limits | 11 Livello 4 · Rischi · limiti e costi di oggi (fix pass: rebuilt as the top four risks of section 15 in its order, one line each, plus one cost line) | 14, 15 | cold start, claude.ai and handbook-copy limits, the cost card details |
| 12 guardrails | 07 Livello 3 · Il controllo delle citazioni | 10, 1 | privacy and legal note replaced by the limit of the check (the privacy facts stay in section 13) |
| 13 next steps | 12 Livello 4 · Prima di un secondo utente (fix pass: one line per node, details moved to the note) | 17 | the stale-page warning |
| 14 decisions | 14 Riferimento · Checklist delle decisioni (fix pass: licences first, tagged as urgent; headline says two more decisions are in the guide) | 24 | the question-count range on the real-questions card; two of the eight decisions (shown in the guide) |
| new | 13 Livello 5 · Il modello per il rollout (three option cards plus a note, existing card pattern) | 19 | not applicable |

## T2

- Deck: 14 slides numbered 01..14, kickers match deep-dive sections in non-decreasing level order, title slide unchanged. Style block, script and the 4 SVG blocks are byte-identical to the base; SVG relative order is architecture, workflow, cloud, local.
- Order was changed by editing text in place, then reordering whole slide blocks by their number with a temporary script (scratch, outside the repository); the old slide 10 block was dropped by label.
- GATE: 37 OK, `RESULT: PASS`. Mutation run: an absent number and a malformed kicker each FAIL their check (2 of 2).
- Deck visible words went from 1,031 to 1,078; per-slide clipping is for the orchestrator's render check.
- Tracer note: the T2 gate passing is the proof that the deck follows the new deep dive end to end.

## T3

- Round-1 findings applied to SRC (then ASSEMBLE) and to the deck. Apply order: rulings first, then the fact-check precedence note, then the style findings.
- Deck edits: title lead and card 2 of slide 2 reworded to the deep-dive wording, slide 4 bodies, slide 5 rebuilt as a tool table, slide 7 cards 2 and 3, slide 8 pills now «superato», slide 11 rebuilt, slide 12 slimmed, slide 13 card A, slide 14 reordered; typographic double quotes replaced by guillemets in all deck text outside the SVGs.
- Mutation checks were not repeated: CHECKS did not change in this pass.

## Review findings

Legend: applied = fixed as suggested (or by the ruling); merged = applied once together with the finding named; rejected = rejected by ruling; open = not applied, with the reason. Totals: 100 findings (40 cold reader, 50 clear-writing, 10 fact check): 99 applied (7 of them merged duplicates, 5 applied in part), 1 rejected by ruling, 0 open.

Cold reader (CR):
- CR1 applied in part by ruling: figures 3 and 4 moved to section 12; section 27 kept as an overview table.
- CR2 applied: MCP analogy, protocol and tool definitions moved to section 2; RAG and custom connector glossed there too.
- CR3 applied: Meridian defined at its first use in section 12; section 18 keeps the licence rule.
- CR4 applied: trace labels in plain words; token and confidence details dropped (they live in sections 8 and 10).
- CR5 applied: the five-defences paragraph cut; the point that the company answers for the bot now sits in section 1.
- CR6 applied: the 0,8 rule lives once in section 9; table row and section 17 sentence removed; Recall@5 is defined inside the rule sentence, its first use, results stay in section 11.
- CR7 applied: the repeated paragraph and bullets of section 1 cut; gap log folded into the «In breve».
- CR8 applied: the limits callout moved to the end of section 11.
- CR9 applied: process sentence cut.
- CR10 applied: JWT, sender check and thread memory moved to section 13; HMAC glossed.
- CR11 applied: login and rate-limit bullets merged into section 13.
- CR12 applied: the reason for two Guides searches stays in section 8 only.
- CR13 applied: history paragraph cut; the rule of no change without a written decision kept in one sentence.
- CR14 applied: noise sentence cut from the «In breve».
- CR15 applied: section 20 reduced to why Google Chat and its limit.
- CR16 applied: priority lists reduced to one paragraph with the first-priority examples.
- CR17 applied in part: rename rejected by ruling; section 25 trimmed to two cases not covered elsewhere, with links to the others.
- CR18 applied: warm-instance note cut from section 12.
- CR19 applied: CI/CD as four numbered steps, tool names reduced.
- CR20 applied: three ways to run the same images; kind glossed.
- CR21 applied: lock-file paragraph cut from section 2.
- CR22 applied: handbook size explained by its point (it fits in a context window, the Guides do not); arithmetic and tag cut.
- CR23 applied: Guides videos introduced before the timestamp.
- CR24 applied: index publishing steps moved to the cloud part of section 12.
- CR25 applied: BM25 wording and bot call counts removed from the tool table (counts stay in section 9).
- CR26 applied: prefix sentence cut; the no-results behaviour kept.
- CR27 applied: Skill defined in one line; three bullets and the limit sentence.
- CR28 applied: one list of sensitive topics, in section 7 (the Skill's table of eight); section 1 and the deck give examples and point to it.
- CR29 applied: agent and protocol names dropped from the section 8 note.
- CR30 applied: «In breve» of section 9 keeps BM25, FTS5 and embedding; RAG moved to section 2.
- CR31 applied: total labelled as including seats, and the seat remark moved below the table.
- CR32 applied: closing paragraph of section 16 cut.
- CR33 applied: meta sentence cut from section 17.
- CR34 applied: Vertex and Bedrock defined before the table; option A marked not yet implemented; client sentence after the table.
- CR35 applied: undefined jargon replaced by plain words; last bullet cut.
- CR36 applied: deck slide 11 rebuilt from the top four risks of section 15, with one cost line.
- CR37 applied: deck slide 5 shows the five tool names with one line each.
- CR38 merged with FC4.
- CR39 applied in part: licences first and tagged urgent; the headline states that two decisions stay in the guide.
- CR40 applied in part: slide 8 shows «superato» (FC2 overrides); slide 12 one line per node; slides 1 and 2 use section 1 wording.

Clear-writing review (CW):
- CW1 to CW6 applied (sections 13, 8, 8, 18, 13).
- CW7 applied: the bot gives the general written rule and says whom to ask (sections 1, 3, 7; deck slides 4 and 7).
- CW8 merged with CR19.
- CW9 applied: three conditions stated, noise dropped (ruling).
- CW10 applied.
- CW11 applied (deck slide 4).
- CW12 applied without naming an agent (ruling): the direction decides, as the base checklist states.
- CW13 to CW19 applied.
- CW20 applied as a cut (ruling, same as CR9).
- CW21 merged with CR8.
- CW22 to CW26 applied.
- CW27 merged with CR10.
- CW28 and CW29 applied.
- CW30 rejected by ruling: the «Quando non serve:» label is the template convention and a gate check.
- CW31 to CW33 applied (HR named in the cleanup sentence because section 17 states that HR rewrites the handbook).
- CW34 applied as a cut (ruling, same as CR13).
- CW35 applied.
- CW36 merged with CR20; CW37 applied with the kind gloss.
- CW38 applied (sections 13 and 16; the sentence in section 7 was cut).
- CW39 applied in active form, no invented agent (ruling).
- CW40 applied: «addestramento».
- CW41 to CW48 applied.
- CW49 merged with FC10 (FC10 overrides).
- CW50 applied (deep dive section 11 and deck slide 8; the cryptic fragment on the deck removed).
- Minor items applied: English terms replaced by Italian ones outside code and tool names, terms unified, first uses of Deep Agents and A2A dropped, Connection replaced, «Guarda» defined in section 4, the 30B figure glossed, guillemets used in the deck, deck slide 12 headline no longer repeats its kicker.

Fact check (FC):
- FC1 applied (same as CW6): planned, not done; column header «Risposta prevista».
- FC2 applied: «superato» in section 11 and on the deck (section 9 table row removed).
- FC3 applied: slide 5 no longer draws claude.ai through the bot.
- FC4 applied: empty-context test described as a test on the golden-set handbook and Guides questions (section 11, slide 7).
- FC5 applied: the bot's request counts stay only in section 9.
- FC6 applied: qualifier restored in section 4.
- FC7 applied: indexing date for the Guides in section 6.
- FC8 and FC9 applied (deck slides 1 and 2).
- FC10 applied (deck slide 14).

## Render check

- Round 1 (orchestrator, before the fix pass): both pages passed at 1440 and at 390 (mobile emulation), per FINDINGS: no page-level horizontal overflow, 4 SVGs visible, 0 broken TOC anchors, deck 14 slides without clipping.
- Post-fix re-run (orchestrator): both pages pass at 1440 and at 390 (mobile emulation). Deep dive: no page-level horizontal overflow, 0 broken in-page anchors, the 4 SVGs sit in s2, s8, s12, s12. Deck: 14 slides, none with overflow or clipped children, slides 5, 11 and 12 included. Gate re-run by the orchestrator: 37 OK, RESULT: PASS; the earlier planning-terms check also passes on both files.

## Gate

Final GATE output (file paths shortened to the file name):

```
OK forbidden-strings deep-dive.html -- 9 entries, no hit
OK clickup-ids deep-dive.html -- 0 match(es)
OK svg-count deep-dive.html -- 4 open, 4 close
OK svg-geometry deep-dive.html -- 4 svg identical to backup
OK unique-ids deep-dive.html -- 54 ids unique
OK anchors deep-dive.html -- 34 links ok
OK section-balance deep-dive.html -- 28 open, 28 close
OK bot-terms deep-dive.html -- 0 bot-gate phrase(s), 0 'gate' in the bot section
OK planning-terms deep-dive.html -- none
OK svg-identical deep-dive.html -- 4 svg identical to base
OK svg-markers deep-dive.html -- 4 marker prefixes, all references local
OK code-paths deep-dive.html -- 75 spans checked
OK old-refs deep-dive.html -- part x0, section-code x0, old-code x0
OK toc deep-dive.html -- 34 links match their targets
OK levels deep-dive.html -- 6 dividers, 6 closing sections in order
OK section-numbers deep-dive.html -- 28 sections numbered 1..28
OK word-count deep-dive.html -- 6145 words; front 273, L1 715, L2 1078, L3 744, L4 1684, L5 947, ref 704
OK dd-numbers deep-dive.html -- no new number token
OK title-block deep-dive.html -- 3 section links, dates only
OK conventions deep-dive.html -- 6 «In breve» boxes (min 5), 6 trade-off notes (min 6)
OK forbidden-strings story-deck.html -- 9 entries, no hit
OK clickup-ids story-deck.html -- 0 match(es)
OK svg-count story-deck.html -- 4 open, 4 close
OK svg-geometry story-deck.html -- 4 svg identical to backup
OK unique-ids story-deck.html -- 23 ids unique
OK anchors story-deck.html -- 0 links ok
OK section-balance story-deck.html -- 0 open, 0 close
OK bot-terms story-deck.html -- 0 bot-gate phrase(s), 0 'gate' in the bot section
OK planning-terms story-deck.html -- none
OK svg-identical story-deck.html -- 4 svg identical to base
OK svg-markers story-deck.html -- 4 marker prefixes, all references local
OK code-paths story-deck.html -- 0 spans checked
OK old-refs story-deck.html -- part x0, section-code x0, old-code x0
OK slides story-deck.html -- 14 slides (max 14), 14 num spans
OK title-slide story-deck.html -- dates only
OK deck-numbers story-deck.html -- every token exists in the deep dive
OK deck-kickers story-deck.html -- 13 kickers match deep-dive sections, levels non-decreasing
RESULT: PASS
```

## Open items

- None from the review loop: no finding was left open.
- Deep-dive length is about 45 words above the 6,100 target (6,145), inside the gate range.
