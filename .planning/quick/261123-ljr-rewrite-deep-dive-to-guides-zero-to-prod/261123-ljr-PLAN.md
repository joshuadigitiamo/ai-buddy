---
phase: quick-261123-ljr
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-checks.py
  - .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-SUMMARY.md
  - docs/internal/work-ljr/assemble.py
  - docs/internal/work-ljr/deep-dive.src.html
  - docs/internal/presentation/deep-dive.html
  - docs/internal/presentation/story-deck.html
autonomous: false
requirements: [quick-261123-ljr]

estimate:
  tokens: 220000
  raw_tokens: 220000
  tasks: 3
  confidence: low

must_haves:
  truths:
    - "The deep dive follows the Guides 'Zero to Production' template in Italian: title 'AI Buddy — Guida completa', subtitle 'Da zero alla produzione', one intro paragraph naming both audiences plus one line pointing managers to the cost, risk and decision sections, a TOC grouped by level with working anchors, level dividers Livello 1..5 then 'Best practice e riferimento', sections numbered 1..N without gaps, and the six closing sections in order (U-3)"
    - "The deep dive holds 5,000-7,000 visible words outside the SVGs (base: about 14,300), has no 'Per la direzione' part and no September appendix; the September research survives only in Livello 5 and the decision checklist (U-1, U-2, U-3)"
    - "No fact is altered or invented: every number token of the new deep dive exists in the base deep dive, every number token of the deck exists in the new deep dive, a non-numeric new fact appears only with a repo pointer listed in SUMMARY, and every fact-check finding is fixed or rejected with a reason"
    - "The deck has at most 14 slides numbered 01..N; every slide after the title carries the kicker 'Livello N · <deep-dive section title>' or 'Riferimento · <title>', in non-decreasing level order; CSS, script and the 4 SVG blocks are unchanged and in their original order"
    - "Every applicable earlier rule still holds on both files: forbidden literals, ClickUp ids, planning terms, SVG geometry and marker prefixes, unique ids, anchors, bot terms, no exact results, no stats in the title block or title slide, no stale cross-references to the old A/B/C sections"
    - "Both files render at 1440 px and 390 px without page-level horizontal overflow, with 4 visible SVGs each, no clipped slide, and working deck navigation (orchestrator render check, run before and after the fix pass)"
    - "The executor loaded the clear-writing skill before writing Italian in every task; three read-only reviewers (cold reader, fact check, clear-writing) ran after T2, and SUMMARY records each finding with how it was resolved (U-4, U-5)"
    - "SUMMARY maps every old section and every old slide to kept / merged into section N / cut with a reason, quotes no handbook text, name or internal id, and the executor stages and commits nothing"
  artifacts:
    - path: .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-checks.py
      provides: "Stdlib gate: the 8 fpj common checks, the k6x planning-terms check, 5 new common checks, 7 deep-dive checks, 4 deck checks (20 lines for the deep dive, 17 for the deck)"
    - path: docs/internal/work-ljr/assemble.py
      provides: "Splices the 4 base SVG blocks verbatim into the deep-dive source at its placeholders (gitignored helper)"
    - path: docs/internal/work-ljr/deep-dive.src.html
      provides: "Hand-written deep-dive source with SVG placeholders; the only file edited for deep-dive text (gitignored)"
    - path: docs/internal/presentation/deep-dive.html
      provides: "Rewritten deep dive, build output of assemble.py (gitignored, never committed)"
    - path: docs/internal/presentation/story-deck.html
      provides: "Story deck aligned to the deep-dive levels and terms (gitignored, never committed)"
    - path: .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-SUMMARY.md
      provides: "Decisions, old-section map, slide map, new facts, review findings with resolutions, final gate output"
  key_links:
    - from: .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-checks.py
      to: .planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-checks.py
      via: "importlib.util.spec_from_file_location; reuses COMMON, SVG_BLOCK, OLD_CODES, _strip_comments, _visible_text"
      pattern: "261123-fpj-checks.py"
    - from: .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-checks.py
      to: .planning/quick/261123-k6x-remove-planning-process-references-from-/261123-k6x-checks.py
      via: "importlib.util.spec_from_file_location; reuses check_planning_terms"
      pattern: "261123-k6x-checks.py"
    - from: .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-checks.py
      to: docs/internal/base-ljr/
      via: "svg-identical and dd-numbers read <parent of the file's dir>/base-ljr/<file name>"
      pattern: "base-ljr"
    - from: docs/internal/work-ljr/deep-dive.src.html
      to: docs/internal/presentation/deep-dive.html
      via: "assemble.py replaces <!--SVG n--> with the n-th <svg> block of docs/internal/base-ljr/deep-dive.html"
      pattern: "<!--SVG [1-4]-->"
    - from: docs/internal/presentation/story-deck.html
      to: docs/internal/presentation/deep-dive.html
      via: "deck-kickers and deck-numbers read the sibling deep-dive.html: kicker titles and number tokens must exist there"
      pattern: 'with_name\("deep-dive.html"\)'
---

<objective>
Rewrite the internal deep dive into the Guides "Zero to Production" structure (five levels plus reference sections), at about 40% of its current length, then align the story deck to the rewrite. Run a review loop (render check plus three read-only reviewers) and a fix pass before closing.

Purpose: the owner finds the current deep dive too long and full of side detail. The Guides template is the structure the owner wants: a newcomer reads it top to bottom from zero, and an experienced engineer or a manager jumps to the level or section they need.

Output: the gate script and SUMMARY (not committed by the executor), a gitignored assembler and deep-dive source, and the two rewritten gitignored files. The orchestrator commits PLAN, SUMMARY, checks.py and STATE.md only after the user's OK.

User decisions (locked, asked today) and added requirements:
- U-1 Length: about 40% of the current text, about 6,000 visible words (gate range 5,000-7,000; base about 14,300). Keep what a newcomer or a reviewer needs at each level; cut repetition, side detail and most of the September research.
- U-2 September research (old Parte C): folded into Livello 5. Keep only what still drives a decision (seats and terms, model choice for the rollout, handbook cleanup and missing pages), condensed into Livello 5 and the decision checklist. No separate appendix.
- U-3 Audience: pure levels, no "Per la direzione" part. Costs, risks and open decisions move into Livello 4 and the decision checklist. One intro line points managers to those sections.
- U-4 The executor loads the clear-writing skill before writing any Italian prose, in the deep dive and in the deck. It is an explicit step of every writing task.
- U-5 After execution the orchestrator runs a render check and three plain read-only reviewers (cold reader, fact check, clear-writing review). Their findings go to an executor fix pass; then the gate and the render check run again. SUMMARY records each finding and its resolution.

Coverage (source item -> task):

| Source item | Task |
|-------------|------|
| Goal: deep dive in the Guides level structure, Italian | T1 (outline, HTML contract, gate checks toc / levels / section-numbers / title-block / conventions) |
| U-1 length | T1 (word-count check, per-level budgets) |
| U-2 September research folded into Livello 5 + checklist | T1 (sections 18-21 and 24; old c1-c7 rows in the section map) |
| U-3 no direction part; costs, risks, decisions in Livello 4 + checklist; manager pointer | T1 (sections 14, 15, 17, 24; title-block check) |
| Writing conventions: analogy first, «In breve» box, tables, «Quando non serve», no filler | T1 (conventions check), T2 for the deck wording |
| Deck alignment: level order, same terms and titles, visual system and SVGs kept, at most 14 slides, slide facts exist in the deep dive | T2 (slides, deck-kickers, deck-numbers, svg-identical checks) |
| Rules in force: no owner name / ids / personal paths, no exact results, no title stats, inline SVG with prefixed markers, no planning terms, facts cut not altered | T1 gate (forbidden-strings, planning-terms, svg-markers, title-block, title-slide, dd-numbers, old-refs); T3 fact-check findings |
| Gate script with the listed checks, run in Docker | T1 |
| Render check at 1440 and 390 | Review hand-back (orchestrator), after T2 and after T3 |
| U-4 clear-writing loaded in each writing task | T1 step 2, T2 step 1, T3 step 1 |
| U-5 review loop, fix pass, gate and render re-run, findings in SUMMARY | Review hand-back + T3 |
| SUMMARY per old section and per slide, no handbook text, names or ids | T1 (section map), T2 (slide map), T3 (findings, gate) |
| No commits by the executor; sequential on the main tree | Every task; verify in T1 and T3 |

Execution is SEQUENTIAL on the main working tree (`workflow.use_worktrees=false` is set): worktrees would not contain the gitignored files. The plan stops once on purpose, at T3's precondition, so the orchestrator can run the review loop.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md

Paths used below (repo-relative, cwd = repository root):
- TASKDIR: `.planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/`
- CHECKS: `TASKDIR/261123-ljr-checks.py`; SUMMARY: `TASKDIR/261123-ljr-SUMMARY.md`
- FPJ: `.planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-checks.py` (224 lines; reuse, never edit)
- K6X: `.planning/quick/261123-k6x-remove-planning-process-references-from-/261123-k6x-checks.py` (230 lines; reuse, never edit). K6X SUMMARY in the same folder shows the SUMMARY shape and the term decisions still in force ("test di accettazione", "passi di lavoro", SVG titles «AI Buddy, architettura attuale» / «AI Buddy, deployment attuale»).
- DD: `docs/internal/presentation/deep-dive.html`; SD: `docs/internal/presentation/story-deck.html` (both gitignored, LF line endings).
- BASE_DD, BASE_SD: `docs/internal/base-ljr/deep-dive.html` and `docs/internal/base-ljr/story-deck.html`. Byte-identical to DD and SD at planning time; the pre-task state and the only undo copy. Never edit BASE. Never touch `docs/internal/presentation/backup-261123/` or `docs/internal/base-k6x/`.
- WORK: `docs/internal/work-ljr/` (gitignored, created by T1). SRC: `WORK/deep-dive.src.html`; ASM: `WORK/assemble.py`; FINDINGS: `WORK/review-findings.md` (written by the orchestrator, read by T3).
- FORBID: `docs/internal/gate-forbidden.txt` (gitignored, one literal per line). Never print its content.
- CW: the clear-writing skill. Load it with the Skill tool (`clear-writing`); if the Skill tool is unavailable, read `~/.claude/skills/clear-writing/SKILL.md` (93 lines) and `~/.claude/skills/clear-writing/references/italian.md` (75 lines) from disk.
- PYSTD: `~/.claude/setup/PYTHON_DOCSTRING_COMMENT_STANDARD.md` (44 lines). Read before writing CHECKS and ASM.
- Repo sources for facts and pointers: `README.md`, `jobs/sync/README.md`, `jobs/eval/README.md`, `services/mcp_server/README.md`, `services/chat_bot/README.md`, `deploy/cloudrun/README.md`, `deploy/k8s/README.md`, `skills/digitiamo-buddy/SKILL.md`, `docs/PLAN.md`, `docs/research/` (September research), `docs/adr/0001-index-handoff.md`.
- Optional model of the template: in the Guides repo, `AI-Engineering/MCP_SERVERS_GUIDE.md` lines 1-64 (locate the Guides root via `~/.claude/setup/GUIDES_INDEX.md`). The HTML contract below already encodes the template; reading the guide is not required.

BASE_DD map (line ranges; read each range once, skip the SVG ranges):
- CSS 11-138; header, «In breve» and TOC 143-195; Parte A 197-416 (a1 199, a2 221, a3 272, a4 293, a5 317, a6 332, a7 364); Parte B 417-1524 (b1 419, b2 492, b3 535, b4 718, b5 752, b6 795, b7 823, b8 967, b9 1005, b10 1358, b11 1443, b12 1476); Parte C 1525-1858 (c1 1527, c2 1557, c3 1595, c4 1638, c5 1672, c6 1714, c7 1839); footer 1859-1865.
- SVG blocks (skip): 541-692 architecture, 829-933 bot workflow, 1031-1176 cloud deployment, 1199-1324 local kind. Figure wrappers and captions: 540-541 and 692-694, 828-829 and 933-936, 1030-1031 and 1176-1179, 1198-1199 and 1324-1327.
- Visible words per old section (outside SVG): a1 364, a2 548, a3 396, a4 220, a5 254, a6 349, a7 613, b1 1043, b2 621, b3 431, b4 462, b5 487, b6 357, b7 599, b8 351, b9 885, b10 698, b11 602, b12 477, c1 463, c2 402, c3 447, c4 421, c5 562, c6 1714, c7 172.

## Commands (Git Bash, cwd = repository root; Bash syntax, not PowerShell)

GATE (this full command wherever the plan says "GATE"):
`GATE_FORBIDDEN="$(cat docs/internal/gate-forbidden.txt)" MSYS_NO_PATHCONV=1 docker run --rm -v "$PWD:/w" -w /w -e GATE_FORBIDDEN python:3.12-slim python -I .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-checks.py docs/internal/presentation/deep-dive.html docs/internal/presentation/story-deck.html`

ASSEMBLE (rebuilds DD from SRC; run after every SRC edit):
`MSYS_NO_PATHCONV=1 docker run --rm -v "$PWD:/w" -w /w python:3.12-slim python -I docs/internal/work-ljr/assemble.py docs/internal/base-ljr/deep-dive.html docs/internal/work-ljr/deep-dive.src.html docs/internal/presentation/deep-dive.html`

`MSYS_NO_PATHCONV=1` is required in Git Bash. `python:3.12-slim` is already local; no image pull and no package install anywhere in this plan.

GATE prints 37 lines `OK|FAIL <check> <file> -- <detail>` (deep dive 20, deck 17), then `RESULT: PASS|FAIL`; exit 0 only if all are OK. Expected outcome per stage:
- CHECKS written, files unchanged: 28 OK, 9 FAIL. Deep dive FAILs: code-paths (one bare file name that is not in the repo), old-refs (62 old A/B/C references at planning time), toc, levels, section-numbers, word-count (about 14,300), title-block, conventions. Deck FAIL: deck-kickers. Everything else OK (deck-numbers OK: every deck number token is already in BASE_DD, measured at planning time). If a check disagrees with this baseline, find out why before editing any page; fix CHECKS only if CHECKS is wrong, and say so in SUMMARY.
- T1 after the skeleton plus Livello 1: deep dive 18 OK, FAIL only word-count and conventions.
- End of T1: all 20 deep-dive lines OK; the deck may FAIL deck-kickers and deck-numbers.
- End of T2 and end of T3: 37 OK, `RESULT: PASS`.

## Deep-dive HTML contract (CHECKS enforces the parts marked [gate])

- Head: copy the BASE_DD `<style>` block. Allowed CSS changes: `nav.toc ol` gets `list-style:none;padding-left:0` (the number is in the link text), and one new `.subtitle` rule (serif, about 20 px, muted). `<title>AI Buddy — Guida completa</title>`; rewrite the meta description.
- `<header>` [gate title-block]: `<p class="eyebrow">` (no number except the state date 23/11/2026), `<h1>AI Buddy — Guida completa</h1>`, `<p class="subtitle">Da zero alla produzione</p>`, one `<p class="lede">` intro paragraph that names the two audiences (who starts from zero, experienced engineers), and one `<p class="muted">` line that points managers to the cost, risk and decision-checklist sections with at least three `<a href="#sN">` links, one of them to the checklist. No number token in the header except dates dd/mm/yyyy. The old top «In breve» box is dropped: its facts live in section 1.
- `<nav class="toc" aria-label="Indice">` [gate toc]: for each group `<p class="tocpart"><a href="#livello-N">Livello N — Nome</a></p>` followed by `<ol>` with `<li><a href="#sN">N. Titolo</a></li>`; last group `<p class="tocpart"><a href="#riferimento">Best practice e riferimento</a></p>`. Link texts equal the target heading texts exactly, in document order; every divider and every section is linked once.
- Level dividers [gate levels], exactly, in order: `<h2 class="part" id="livello-1">Livello 1 — Base</h2>`, `livello-2` «Livello 2 — Intermedio», `livello-3` «Livello 3 — Avanzato», `livello-4` «Livello 4 — Produzione», `livello-5` «Livello 5 — Ecosistema e scelte», then `<h2 class="part" id="riferimento">Best practice e riferimento</h2>`. The em dash is U+2014. The existing `.part` CSS styles them.
- Sections [gate section-numbers]: `<section id="sN">` with `<h2>N. Titolo</h2>` as its first element, N = 1..28 continuous across levels; no `.snum` span. Titles are short (at most about 45 characters): they double as deck kickers.
- Closing sections [gate levels], exactly these six after the `riferimento` divider, in order, title starting with: «Errori comuni», «Checklist delle decisioni», «Casi d'uso reali», «Riferimento rapido», «Il quadro d'insieme», «Fonti».
- «In breve» box [gate conventions, at least 5]: `<div class="callout note"><h3>In breve</h3><p>…</p></div>`, after a one- or two-sentence analogy, for each hard concept.
- Trade-off note [gate conventions, at least 6]: a paragraph that starts with `<strong>Quando non serve:</strong>` or `<strong>Quando è eccessivo:</strong>`. Each note restates a trade-off or scope limit that BASE_DD already states (candidates: embeddings and vector DB while keyword search on the Guides is above 0,8; multiple agents for Q&A; per-section ACL; the whole handbook in context; self-hosting only with a formal data-residency constraint; the personal Max only for one user; a minimum instance only if users grow; writing to the HR system only after a stable rollout; the Skill without a code check). No invented trade-off.
- Tables inside `<div class="tblwrap">`. Cross-references as `<a href="#sN">sezione N</a>`, never «A3», «B9», «Parte C» [gate old-refs].
- Figures: `<figure class="dd-fig"><div class="diagram-container"><!--SVG n--></div><figcaption>…</figcaption></figure>`, placeholders in this order: `<!--SVG 1-->` architecture in section 2, `<!--SVG 2-->` bot workflow in section 8, `<!--SVG 3-->` cloud deployment and `<!--SVG 4-->` local kind in section 27. ASSEMBLE splices the BASE_DD blocks verbatim, so the SVG order and markup stay as in BASE [gates svg-identical, svg-geometry, svg-markers]. Rewrite captions only to drop old references. Never write SVG markup by hand.
- Section 8 (the bot workflow, holding SVG 2) must not contain the letters «gate» anywhere, not even inside a `<code>` span or a word such as «gateway» [fpj gate bot-terms].
- A short `<footer>` stays (state date; local file, excluded from the public repository).

## Outline (Claude's discretion; titles may be reworded, keep them short and keep the closing titles above)

Budgets are visible words outside SVG; the gate checks only the total (5,000-7,000) and prints the per-part counts.

Front matter (header, TOC): at most 350.

Livello 1 — Base (at most 800)
| N | Title | From BASE_DD | Keep, in general terms |
|---|-------|--------------|------------------------|
| 1 | Cos'è AI Buddy | header lede, top «In breve», a1, a2 intro and its "what the result does not say" box, a7 first answer | what it answers and from which two sources; always cites; «non lo so, chiedi a …» plus gap log; sensitive topics go to a person; the risk it is built against (invented policy, the 2024 court case); company context (size, tools, one developer, one user); measured on a 40-question golden set, acceptance test passed on 22/11/2026, and the limits of that result. Analogy plus «In breve». |
| 2 | L'architettura in un disegno | b3 intro, a2 "what exists today", SVG 1 with caption | the parts (sync and index, MCP server, bot, Skill for claude.ai) and how they connect; Docker everywhere in one line. |
| 3 | Una domanda dall'inizio alla fine | b8 main trace | the leave-request trace, with the base note that the answer text is indicative; the no-source branch in two lines. |

Livello 2 — Intermedio (at most 1,150)
| 4 | Le due fonti: handbook e Guides | b2 | handbook size (pages, words, tokens); local copy instead of ClickUp, never in the public repo; Guides count and size; Guides still personal (decision in section 24). |
| 5 | L'indice e il sync | b3 "new index version" and "Docker everywhere", a2 sync bullet | manual sync on the development laptop; masking of credentials and sensitive data; `index.db`, private bucket, manifest with hash and size. |
| 6 | I cinque tool MCP | b4, b3 "choices that keep the server small", b1 MCP / tool / connector entries | analogy plus «In breve» on MCP; the five tools, each output carries its source; fewer than 10 tools with name prefixes; who may call them (Google login with exact domain, the bot's ID token); errors written for the model in one line. |
| 7 | La Skill digitiamo-buddy | b6 | what the Skill holds; its limit (instructions, no code check; the bot is what was measured). |
| 8 | Il workflow del bot | b7, SVG 2 with caption, b1 LangGraph entry | fixed workflow (riformula, cerca, risponde, controlla), not an agent; models per step; thread memory (turns, HMAC, 24 h); what the user sees; who may use it (JWT, `ALLOWED_USERS`). No «gate» letters (contract above). |

Livello 3 — Avanzato (at most 800)
| 9 | La ricerca: parole chiave prima degli embedding | b5, b1 BM25 / embedding entries | keyword search on both sources and why it suits technical questions; the upgrade criterion written in advance (Recall@5 ≥ 0,8, else hybrid search); the second search on the Guides. «In breve». |
| 10 | Il controllo delle citazioni | a1 bullet, b7 check step, a7 "what if the bot gets a policy wrong", b8 contradictory-handbook note | analogy plus «In breve»: every citation must match a source found in the same run, otherwise «non lo so»; the check proves the source exists, not that it is right; the five defences. |
| 11 | Misurare prima di dichiarare | b10, a2 measurement table, b1 golden-set / Recall entries | golden set (40 questions by category, written by Claude, reviewed by the developer); bot models and the separate judge; empty-context test; thresholds with «superato»; the eval command `<code>` span; why the judge marks an answer wrong (two lines); the four changes approved before the final run (one or two lines). The KPI table is cut or reduced to one line in section 17. «In breve». |

Livello 4 — Produzione (at most 1,300)
| 12 | Deploy: Cloud Run, CI/CD, kind e compose | b9 without costs | same images in two environments plus compose; Cloud Run in europe-west8, two services, Meridian sidecar, keyless deploy; CI steps condensed; kind with emulators; a short cloud-versus-local table; link to the figures in section 27. |
| 13 | Sicurezza, privacy e normativa | b11, a5 risk 2, a7 privacy answer | OAuth proxy and token checks in short; norms table condensed (Statuto art. 4 with the Garante measure, AI Act art. 50, L. 132/2025, GDPR); gap log without user id, deleted after 90 days; thread memory HMAC, 24 h; consumer-plan training until the API switch. |
| 14 | Costi | a4, b9 costs, a7 cost answer, c5 recalculation | today versus a 15-user rollout (seats, API, infrastructure, total, annual-billing figures); real cost not yet measured; items nobody has estimated. |
| 15 | Rischi | a5, b9 "two accepted limits" | the seven risks, one line each, with who handles them; cold-start and Meridian-login facts. |
| 16 | Cosa è verificato e debiti tecnici | b12 | verified/open table condensed, confidence tags kept; known technical debts; the closing summary in one or two sentences. |
| 17 | Prima di un secondo utente | a6 | the seven items, one line each; after the pilot, in short. |

Livello 5 — Ecosistema e scelte (at most 750)
| 18 | Licenze: un seat per persona | c4, a3 first row, a7 answers on seats and on the personal Max | what the terms allow; shared Max accounts already break the consumer terms; Team seats (cost in section 14); how AI Buddy reaches Claude today (Meridian, one user, three controls) and the switch to an API key. «In breve» on Meridian. |
| 19 | Il modello per il rollout | c6, a3 sovereignty row, a7 data-residency answer | options A/B/C (model, where, cost per month, when to choose); the golden set decides (same questions, same thresholds); open models need the bot's citation check; option C cold start in one line; the open sovereignty question and the DPO dependency. Cut: shortlist detail, VRAM, excluded models, serving, hosting table, utilisation arithmetic, the bare `compose.yaml` span. |
| 20 | Il canale: Google Chat | c7, c5 "two roads" | why Google Chat (ClickUp dismissal closed the question); connector and bot built together so the acceptance test also measures the bot. |
| 21 | Handbook: pulizia e pagine mancanti | c1, c2 | the inventory found thirteen problems (general terms, no handbook text); why cleanup comes first; missing pages by priority (categories only); how to write pages a bot uses well (one topic per page, the frontmatter fields). |
| 22 | Quando AI Buddy non è lo strumento giusto | a6 out of scope, c3 anti-patterns | out-of-scope items; not a replacement for the human buddy; no per-person surveillance. |

Best practice e riferimento (at most 900, footer included)
| 23 | Errori comuni | a1, a5, b8, c1, c3, c6 | table «Errore / Cosa succede / Come lo evita AI Buddy», 5-7 rows, every fact from BASE_DD. |
| 24 | Checklist delle decisioni | a3, b2 Guides note | the eight decisions as a table «Decisione / Chi / Quando serve», the urgent one first. |
| 25 | Casi d'uso reali | b8 contradictory and no-answer cases, b7 "what the user sees", a1 sensitive topics | short cases: answer with source, contradictory handbook, no source, Guides answer with video, sensitive topic. |
| 26 | Riferimento rapido | base `<code>` spans, b10 thresholds, b4 tools | commands (sync and publish, unit tests, eval command, kind up and smoke), the five tools, thresholds, key settings (`LLM_BACKEND` values, `ALLOWED_USERS`, region). |
| 27 | Il quadro d'insieme | SVG 3 and SVG 4 with captions | the two deployment figures; one line pointing back to the section 2 figure. |
| 28 | Fonti | footer | the repo sources listed in this context as `<code>` paths, the Guides used, the September research; the note that the document holds no credentials, project ids or handbook text beyond page titles. Never a planning path. |

Old content cut entirely unless a row above keeps part of it: b1 glossary as a block (terms are defined at first use or in «In breve»), a7 as a Q&A block (its answers feed sections 1, 13, 14, 18, 19), c3 onboarding statistics, most of c6.

## Story deck: suggested mapping (Claude's discretion within the rules)

| New | Kicker | From old slide |
|-----|--------|----------------|
| 01 | «Stato al 23/11/2026» (title slide, unchanged kicker, no stats) | 01 |
| 02 | Livello 1 · Cos'è AI Buddy | 02 (plus the headline of 03) |
| 03 | Livello 1 · L'architettura in un disegno | 04 (SVG 1) |
| 04 | Livello 1 · Una domanda dall'inizio alla fine | 06 |
| 05 | Livello 2 · I cinque tool MCP | 03 (the flow, reworded to section 6 facts) |
| 06 | Livello 2 · Il workflow del bot | 05 (SVG 2) |
| 07 | Livello 3 · Il controllo delle citazioni | 12 (guardrails; its privacy note moves to slide 11 or 12, or is cut) |
| 08 | Livello 3 · Misurare prima di dichiarare | 07 |
| 09 | Livello 4 · <section 12 title> · cloud | 08 (SVG 3) |
| 10 | Livello 4 · <section 12 title> · locale | 09 (SVG 4); old 10 is cut or reduced to its note |
| 11 | Livello 4 · Costi (or Rischi) | 11 |
| 12 | Livello 4 · Prima di un secondo utente | 13 |
| 13 | Livello 5 · Il modello per il rollout (or Licenze) | new, from sections 18-19, using an existing card or table pattern |
| 14 | Riferimento · Checklist delle decisioni | 14 |

Deck rules:
- Change only: the order of text slides, kicker / h2 / body / card / node / table text, `<span class="num">` values (01..N in order), the HTML comment label before each slide. A text slide may be cut, merged, or added (at most one, reusing an existing slide pattern and accent). Never touch `<style>`, `<script>`, the SVG blocks or the `.slide.diag` structure; the four SVG slides keep their relative order (architecture, workflow, cloud, local) [gates svg-identical, svg-geometry].
- Kicker of every slide after the first [gate deck-kickers]: `Livello N · <deep-dive section title without its number>` or `Riferimento · <closing section title>`, optionally followed by ` · <short suffix>`; the section must sit in that level; levels never go back.
- Same terms as the deep dive (for example «test di accettazione», «controllo delle citazioni», «gap log», «passaggio a una persona»).
- Every fact on a slide exists in the new deep dive [gate deck-numbers for numbers; fact-check reviewer for the rest]. If a slide fact is missing from the deep dive, cut it from the slide; restore it in SRC only if section budgets allow and the fact matters to a newcomer.
- No stats on the title slide [gate title-slide]. Keep each slide's text no longer than the old slide it replaces: the render check fails on a clipped slide.

## Rules for every edit (both files)

- No fact changes: a fact may be cut, never altered. No new number token at all [gates dd-numbers, deck-numbers]. A non-numeric new fact is allowed only if a grep shows a repo source (list above) states it; give it a `<code>` pointer [gate code-paths checks existence] and list it in SUMMARY "## New facts".
- Thresholds and «superato» only; never an exact gate or eval result [FORBID covers known literals]. No owner name: roles only («lo sviluppatore», «il responsabile del progetto», «laptop di sviluppo»). No internal ids, no personal paths.
- Banned words outside `<code>` spans in either file, HTML comments and CSS included [k6x gate planning-terms]: «fase», «fasi», «milestone», «gate», «GSD», `.planning`, phase file names, decision or requirement ids. Use the K6X terms instead.
- Language: Italian. Load CW before writing; apply its rules and final check to every sentence written; one name per concept across both files. Analogy first for hard concepts, then «In breve»; tables for comparisons; no filler.
- Edit deep-dive text only in SRC, then run ASSEMBLE; never edit DD directly (SRC and DD would diverge). Edit SD in place with Edit; take each `old_string` from a Read of the raw HTML, entities included.
- Read BASE_DD by ranges (map above), each range once; never Read a whole HTML file.
- SUMMARY is committed to a public repo: describe content by topic (for example "cost table for a 15-user rollout"), never quote handbook text, names or internal ids.

## Review hand-back (orchestrator, outside GSD; U-5)

After T2 the executor reaches T3, finds FINDINGS missing (T3's precondition) and returns to the orchestrator. This stop is planned. The orchestrator then:
1. Render check. Serve the folder read-only on localhost only, for example `MSYS_NO_PATHCONV=1 docker run --rm -d --name ljr-render -p 127.0.0.1:8765:8000 -v "$PWD/docs/internal/presentation:/srv:ro" -w /srv python:3.12-slim python -m http.server 8000` (or open the files directly if the browser tools accept file URLs). With the Chrome browser tools, on both pages, at viewport widths 1440 and 390:
   a. no page-level horizontal overflow: `document.documentElement.scrollWidth <= document.documentElement.clientWidth`;
   b. 4 SVG elements, each with a bounding-box height above 0 once scrolled into view;
   c. deck: no `.slide` with `scrollHeight > clientHeight + 1` or `scrollWidth > clientWidth + 1` (slides hide overflow, so this means clipped text);
   d. deck: the End key makes the HUD read `NN / NN` (NN = slide count), Home gives `01 / NN`, ArrowRight then gives `02 / NN`;
   e. deep dive: two TOC links scroll to their sections; a screenshot of the header and the TOC at 390 shows no overlapping text.
   Then `docker stop ljr-render`. If the tools cannot set a 390 px viewport, record that step as not run.
2. Three plain read-only reviewer agents (not GSD agents), in parallel. Each gets DD, SD, BASE_DD, BASE_SD, the repo source list above and the rules in force (no owner name or ids; thresholds and «superato» only). They edit nothing and never read `.env`:
   - cold reader: is the deep dive clear to a newcomer and in zero-to-production order; is anything still verbose, repeated or useless; does the deck follow the same order and terms?
   - fact check: does every claim in DD and SD match BASE_DD / BASE_SD or the repo code and READMEs (including `docs/research/`)? Flag every altered, wrongly merged or unsupported claim;
   - clear-writing review: loads the clear-writing skill and reviews the Italian of DD and SD against its rules and its Italian reference.
3. Write FINDINGS (`docs/internal/work-ljr/review-findings.md`, gitignored): render-check results first, then one row per finding: `F-NN | reviewer | location (section N or slide N) | finding | suggested fix`. A reviewer without findings gets one line saying so.
4. Resume: a continuation executor runs T3.
5. After T3: run step 1 again. If a render step fails, append the failures to FINDINGS as new F-NN rows and run T3 again. After two T3 rounds with open failures, stop and ask the user.

## Repo hygiene

- No `git add`, no `git commit`, no `git stash`, no branch change. The orchestrator commits after the user's OK.
- Never read `.env`. Never print FORBID.
- No app or test file changes, so `./run-unit-tests.sh` does not apply (ruff excludes `.planning` and `docs`; mypy lists its own paths).
- If context runs short inside a task: finish the current section, run ASSEMBLE and GATE, append progress to SUMMARY ("## Progress": sections done, next section), and stop. A fresh executor reads CW, SUMMARY and this plan, then continues.
</context>

<tasks>

<task type="tracer">
  <name>Task 1: Tracer: gate and assembler, then the deep dive end to end (skeleton plus Livello 1 first, then all levels)</name>
  <files>.planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-checks.py, docs/internal/work-ljr/assemble.py, docs/internal/work-ljr/deep-dive.src.html, docs/internal/presentation/deep-dive.html, .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-SUMMARY.md</files>
  <read_first>
    - CW (Skill tool `clear-writing`, or SKILL.md plus references/italian.md from disk) and PYSTD
    - FPJ and K6X checks (whole; reuse their names, never edit them) and the K6X SUMMARY (shape, term decisions)
    - BASE_DD by the ranges in the context map, skipping the SVG ranges; the four figure wrapper ranges
  </read_first>
  <behavior>
    CHECKS (stdlib only, Python 3.12, type hints, Google docstrings per PYSTD; read files as bytes, decode UTF-8, normalise CRLF to LF):
    - Loads FPJ and K6X with `importlib.util.spec_from_file_location` from `Path(__file__).resolve().parent.parent / <folder> / <file>`. Reuses FPJ `COMMON` (8 checks) unchanged, FPJ `SVG_BLOCK`, `OLD_CODES`, `_strip_comments`, `_visible_text`, and K6X `check_planning_terms`.
    - Own `main(argv)`: per file, checks = COMMON + (DEEP_DIVE_ONLY if "deep-dive" in the file name else DECK_ONLY); prints `OK|FAIL <check> <file> -- <detail>` per check, then `RESULT: PASS|FAIL`; returns 0, 1, or 2 on a usage error. One comment line says why FPJ main is not reused (it has no deck-only group).
    - BASE = `path.parent.parent / "base-ljr" / path.name`; missing -> FAIL "base missing". visible(x) = `html.unescape(fpj._visible_text(x))`; visible_no_svg removes SVG blocks first. Number tokens: `\d+(?:[.,/]\d+)*`.
    - COMMON adds, after FPJ's 8: planning-terms (K6X function); svg-identical (`SVG_BLOCK.findall` lists equal to BASE); svg-markers (per SVG block: every `<marker>` id has the same prefix before its first "-", prefixes differ across blocks, every `url(#X)` in a block names an id defined in that block); code-paths (inner text of each `<code>` span, tags stripped and unescaped: if it matches `^[\w.-]+(?:/[\w.{}<>*-]+)+/?$` without ":" it must exist relative to the cwd and must not start with `.planning` or `docs/internal`; if it matches `^[\w.-]+\.(?:md|sh|py|ya?ml|toml|txt|lock|json)$` it must exist at the repo root or as a file name anywhere under the repo, walking with `os.walk` and skipping `.git`, `.venv`, `.planning`, `.idea`, `.ruff_cache`, `__pycache__`, `node_modules` and `docs/internal`; spans in `NOT_REPO_PATHS: dict[str, str]` are skipped, starting with `GUIDES_INDEX.md` (file of the Guides repo) and `vllm/vllm-openai` (container image name); FAIL detail lists the missing spans); old-refs (on visible_no_svg: counts of `Parte [ABC]\b`, `\b[ABC]\d{1,2}\b` and FPJ `OLD_CODES`; OK only if all are 0; detail shows category counts).
    - DEEP_DIVE_ONLY: toc (inside `<nav class="toc"...>`, the list of (href, normalised link text) equals the list of (id, normalised heading text) of all targets in document order; targets are the dividers `<h2 class="part" id="(livello-[1-5]|riferimento)">` and the sections `<section id="(s\d+)">` followed by `<h2>`; normalised = tags stripped, unescaped, whitespace collapsed; FAIL detail names the first mismatching position and ids, never text); levels (divider ids and texts exactly as in the HTML contract, in order; at least one section after each divider; no section before the first divider; after `riferimento` exactly the six closing sections, titles after "N. " starting with the contract prefixes in order, with the apostrophe U+2019 normalised to an ASCII apostrophe; no id `parte-a`, `parte-b` or `parte-c`); section-numbers (the k-th section has id `s{k}` and a heading starting `"{k}. "`, k = 1..N); word-count (`len(visible_no_svg.split())` between 5000 and 7000 inclusive; detail shows the total and the counts of front matter, L1..L5 and the reference part); dd-numbers (before tokenising the new file, remove the `N. ` prefix right after a section `<h2>`, the whole text of every `<a href="#s\d+">` link, and the text `Livello [1-5]`; the new token set must be a subset of the BASE token set, BASE tokenised without stripping; FAIL detail lists the new tokens); title-block (inside `<header>`: h1 text equals «AI Buddy — Guida completa»; the text contains «Da zero alla produzione»; every number token is a date `\d{2}/\d{2}/\d{4}`; at least three `href="#s\d+"` links, one of them to the section whose title starts «Checklist delle decisioni»); conventions (count of `<h3>In breve</h3>` at least 5; count of `<strong>Quando non serve` plus `<strong>Quando è eccessivo`, on the unescaped raw text, at least 6).
    - DECK_ONLY: slides (count of `<div class="stage">` between 1 and 14; the `<span class="num">` values equal 01..N in order, one per slide); title-slide (the first slide's visible text, `num` span removed: every number token is a date); deck-numbers (deck visible text with every `<span class="num">` and `<span class="n">` element removed: its token set is a subset of the token set of `path.with_name("deep-dive.html")`, full visible text, no stripping; missing file -> FAIL; detail lists the missing tokens); deck-kickers (for every slide after the first, the kicker text matches `^(?:Livello ([1-5])|Riferimento) · (.+)$`; the rest equals a deep-dive section title without its number, or starts with that title plus " · "; that section sits in the kicker's level, Riferimento counting as level 6; levels never decrease; FAIL detail names the slide number and the reason).
    - Output lines: 20 for the deep dive, 17 for the deck. CHECKS holds no FORBID literal and no page text.

    ASM (stdlib, type hints, docstring per PYSTD): arguments BASE_DD, SRC, OUT. Finds the `<svg ...>...</svg>` blocks of BASE_DD (exactly 4, else exit 1); requires each placeholder `<!--SVG 1-->`..`<!--SVG 4-->` exactly once in SRC and no other `<svg` in SRC (else exit 1 with a message naming the placeholder); replaces placeholder n with block n verbatim; writes OUT as UTF-8 with LF; prints `assembled: 4 svg`.
  </behavior>
  <action>
    1. Confirm the start state: `cmp` DD against BASE_DD and SD against BASE_SD (both identical at planning time). If either differs, stop and report: BASE must be the pre-task state.
    2. Load CW before any Italian prose (per U-4), and read PYSTD.
    3. Write CHECKS with the Write tool per the behavior block; module docstring: purpose, the GATE command, the GATE_FORBIDDEN variable, BASE, the NOT_REPO_PATHS rule (add an entry only for a span that names something outside this repo, with the reason). Run GATE on the unchanged files and compare with the expected baseline in the context (28 OK, 9 FAIL). If a check disagrees, find out why before writing any page.
    4. Write ASM. Create SRC (per U-3 and the HTML contract): head with the copied CSS and the two allowed CSS changes, header, the full TOC, all six dividers, all 28 sections with their final headings, the four SVG placeholders in their sections with rewritten captions, the footer, and Livello 1 (sections 1-3) fully written. Write SRC in pieces if needed: one Write for the skeleton, then one Edit per section body. Run ASSEMBLE, then GATE: the deep dive should show 18 OK with FAIL only on word-count and conventions. This proves the structure, the SVG splice and the gate end to end before the bulk of the writing.
    5. Fill Livello 2 to Livello 5 and the six reference sections per the outline (per U-1 and U-2: September research only in sections 18-21 and 24; per U-3: costs, risks and decisions in sections 14, 15, 17 and 24). After each level: ASSEMBLE, GATE, and read the word-count detail against the level budget. Apply CW to every sentence. For each non-numeric fact not in BASE_DD, grep the repo source first and record it for "## New facts"; drop the fact if no source states it.
    6. Run GATE until all 20 deep-dive lines are OK, then the mutation command in verify. If a mutation result is wrong, fix CHECKS and rerun GATE.
    7. Create SUMMARY (English, general terms) with frontmatter `phase: quick-261123-ljr`, `plan: 01`, `status: in-progress`, `commits: 0`, and sections: "## Decisions" (final titles if reworded, SVG placement, dropped top «In breve», word count per part, any NOT_REPO_PATHS entry with its reason); "## Section map" with one row per old block (header and top «In breve», TOC, a1..a7, b1..b12, c1..c7, footer) and columns Old block (id and topic), Outcome (kept in section N / merged into section N / cut), Reason; "## New facts" (fact topic, repo source path) or "none"; "## T1" (GATE OK/FAIL counts before and after, mutation result).
  </action>
  <verify>
    <automated>cmp -s docs/internal/base-ljr/story-deck.html docs/internal/presentation/story-deck.html; echo $?</automated>
    T1 does not touch the deck: [HEAD=0 EXPECT==0 GUARD MUTATION: any T1 edit to SD makes cmp print 1]
    <automated>GATE_FORBIDDEN="$(cat docs/internal/gate-forbidden.txt)" MSYS_NO_PATHCONV=1 docker run --rm -v "$PWD:/w" -w /w -e GATE_FORBIDDEN python:3.12-slim python -I .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-checks.py docs/internal/presentation/deep-dive.html docs/internal/presentation/story-deck.html | grep -c '^OK [a-z0-9-]* docs/internal/presentation/deep-dive.html '</automated>
    All 20 deep-dive checks OK (CHECKS not written yet; predicted 12 on the unchanged file): [HEAD=absent EXPECT==20]
    <automated>MSYS_NO_PATHCONV=1 GATE_FORBIDDEN=x docker run --rm -v "$PWD:/w" -w /w -e GATE_FORBIDDEN python:3.12-slim sh -c 'mkdir -p /tmp/m/internal/presentation /tmp/m/internal/base-ljr && cp docs/internal/base-ljr/deep-dive.html /tmp/m/internal/base-ljr/ && sed -e "s#</footer>#<p>4242 <code>no/such/file.md</code></p></footer>#" -e "0,/<a href=\"#s2\">/s//<a href=\"#s2\">x/" -e "s#<h2>3\. #<h2>33. #" docs/internal/presentation/deep-dive.html > /tmp/m/internal/presentation/deep-dive.html && python -I .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-checks.py /tmp/m/internal/presentation/deep-dive.html' | grep -c -E '^FAIL (dd-numbers|code-paths|toc|section-numbers) '</automated>
    Mutation: a new number, a pointer to a missing file, a changed TOC link text and a skipped section number each FAIL their check: [HEAD=absent EXPECT==4]
    <automated>grep -c -i -F -f <(sed '/^ *$/d' docs/internal/gate-forbidden.txt) .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-checks.py</automated>
    CHECKS holds no FORBID entry: [HEAD=absent EXPECT==0]
    <automated>git ls-files --error-unmatch .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-checks.py >/dev/null 2>&1; echo $?</automated>
    CHECKS is not in the index: [HEAD=1 EXPECT==1 GUARD MUTATION: `git add` of CHECKS makes it print 0]
  </verify>
  <done>
    CHECKS runs 37 checks with the expected baseline and mutation results. DD is the ASSEMBLE output of SRC: Guides structure, 28 numbered sections over five levels plus the reference part, 5,000-7,000 visible words, no number missing from BASE_DD, 4 SVGs identical to BASE in their original order, all 20 deep-dive checks OK. SD is untouched. SUMMARY holds Decisions, Section map, New facts and T1. Nothing is staged or committed.
  </done>
</task>

<task type="auto">
  <name>Task 2: Align the story deck to the rewritten deep dive</name>
  <files>docs/internal/presentation/story-deck.html, .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-SUMMARY.md</files>
  <read_first>
    - CW, if this task runs in a fresh context
    - SUMMARY "## Decisions" and the DD TOC (Grep `href="#s` in DD for the final section titles)
    - SD lines 175-236 (slides 1-4 up to the first SVG), 389-396, 500-550, 696-705, 830-930 (text slides and the lines around each SVG); never Read the `<style>` block, the `<script>` block or an SVG range
  </read_first>
  <action>
    1. Load CW before writing any Italian (per U-4).
    2. Apply the deck mapping and deck rules in the context: reorder the text slides by level, reword kickers to `Livello N · <section title>` or `Riferimento · <title>`, and reword h2, body, card, node and table text to the deep-dive terms. Move a text slide with two Edits (cut, then paste at its new place); never move or edit an SVG block. Renumber the `<span class="num">` values 01..N and update each slide's HTML comment label. Keep at most 14 slides and no stats on the title slide. Per U-3, no «Per la direzione» kicker remains.
    3. Run GATE. For each deck-numbers FAIL, cut the number from the slide, or restore the fact in SRC (then ASSEMBLE) only if it matters to a newcomer and the word count stays at or under 7,000. For each deck-kickers FAIL, fix the kicker to a real section title of the right level. Repeat until `RESULT: PASS` with 37 OK.
    4. Run the deck mutation command in verify.
    5. Append to SUMMARY: "## Slide map" with one row per old slide (old number and topic, new number and kicker or "cut", the deep-dive section holding its facts, facts cut from the slide) and one row per added slide; "## T2" with the GATE counts and the mutation result.
    6. Stop after T2 and return to the orchestrator: T3's precondition (FINDINGS) is unmet by design, and the orchestrator now runs the review hand-back.
  </action>
  <verify>
    <automated>GATE_FORBIDDEN="$(cat docs/internal/gate-forbidden.txt)" MSYS_NO_PATHCONV=1 docker run --rm -v "$PWD:/w" -w /w -e GATE_FORBIDDEN python:3.12-slim python -I .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-checks.py docs/internal/presentation/deep-dive.html docs/internal/presentation/story-deck.html | grep -c '^OK '</automated>
    All 37 checks OK on both files (predicted 28 on the unchanged files): [HEAD=absent EXPECT==37]
    <automated>GATE_FORBIDDEN="$(cat docs/internal/gate-forbidden.txt)" MSYS_NO_PATHCONV=1 docker run --rm -v "$PWD:/w" -w /w -e GATE_FORBIDDEN python:3.12-slim python -I .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-checks.py docs/internal/presentation/deep-dive.html docs/internal/presentation/story-deck.html | tail -n 1 | grep -c '^RESULT: PASS$'</automated>
    Gate passes: [HEAD=absent EXPECT==1]
    <automated>MSYS_NO_PATHCONV=1 GATE_FORBIDDEN=x docker run --rm -v "$PWD:/w" -w /w -e GATE_FORBIDDEN python:3.12-slim sh -c 'mkdir -p /tmp/d/internal/presentation /tmp/d/internal/base-ljr && cp docs/internal/base-ljr/story-deck.html /tmp/d/internal/base-ljr/ && cp docs/internal/presentation/deep-dive.html /tmp/d/internal/presentation/ && sed -e "s#</body>#<p>4243</p></body>#" -e "0,/<p class=\"kicker\">Livello 1 /s//<p class=\"kicker\">Livello 1 x/" docs/internal/presentation/story-deck.html > /tmp/d/internal/presentation/story-deck.html && python -I .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-checks.py /tmp/d/internal/presentation/story-deck.html' | grep -c -E '^FAIL (deck-numbers|deck-kickers) '</automated>
    Mutation: a number absent from the deep dive and a malformed kicker each FAIL their check: [HEAD=absent EXPECT==2]
  </verify>
  <done>
    SD follows the deep-dive level order with kickers that name real deep-dive sections, uses the same terms, keeps its CSS, script and the 4 SVGs unchanged and in order, has at most 14 slides numbered 01..N, and holds no number missing from the deep dive. GATE prints 37 OK and `RESULT: PASS`. SUMMARY holds the Slide map and T2. The executor has returned to the orchestrator for the review hand-back.
  </done>
</task>

<task type="auto">
  <name>Task 3: Fix pass on the review findings, gate re-run, SUMMARY close</name>
  <precondition>docs/internal/work-ljr/review-findings.md exists and is non-empty: the orchestrator wrote it after the render check and the three read-only reviewers (context "Review hand-back"). If it is missing, stop and return to the orchestrator; this is the planned hand-back point.</precondition>
  <files>docs/internal/work-ljr/deep-dive.src.html, docs/internal/presentation/deep-dive.html, docs/internal/presentation/story-deck.html, .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-SUMMARY.md</files>
  <read_first>
    - CW
    - FINDINGS (whole, once), SUMMARY "## Decisions", "## Section map" and "## Slide map"
    - For each finding, only the SRC or SD range it names (Grep for the section id or slide number first)
  </read_first>
  <action>
    1. Load CW before writing any Italian (per U-4).
    2. Decide each finding (per U-5): fix it, or reject it with a reason. Reject only when the fix would add a fact that neither BASE nor a repo source states, break U-1, U-2 or U-3 or a rule for every edit, change an SVG, or contradict CW. A fact-check finding that a claim is altered or unsupported is always fixed: restore the base wording of the fact or cut the claim. Render findings: shorten the text of a clipped slide; wrap an overflowing table in `tblwrap` or shorten it.
    3. Apply deep-dive fixes in SRC, then ASSEMBLE; apply deck fixes in SD with Edit. Apply CW to every changed sentence.
    4. Run GATE until 37 OK and `RESULT: PASS`.
    5. Append to SUMMARY: "## Review findings" (one row per finding: F-NN, reviewer, location, the finding in general terms with no handbook text, names or ids, resolution as "fixed: what changed" or "rejected: reason"); "## Render check" (the orchestrator's results in general terms; mark the post-fix re-run as pending, the orchestrator completes it); "## Gate" with the final GATE output, file paths shortened to the file name. Set frontmatter `status: complete`. Note that BASE keeps the pre-task copies until the user reviews the files.
    6. Run the hygiene checks in verify, then return to the orchestrator for the render re-check (hand-back step 5). If the orchestrator sends new render findings, repeat steps 2-6 on them.
  </action>
  <verify>
    <automated>test -s docs/internal/work-ljr/review-findings.md; echo $?</automated>
    The hand-back happened, FINDINGS exists: [HEAD=1 EXPECT==0]
    <automated>GATE_FORBIDDEN="$(cat docs/internal/gate-forbidden.txt)" MSYS_NO_PATHCONV=1 docker run --rm -v "$PWD:/w" -w /w -e GATE_FORBIDDEN python:3.12-slim python -I .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-checks.py docs/internal/presentation/deep-dive.html docs/internal/presentation/story-deck.html | grep -c '^OK '</automated>
    All 37 checks OK after the fixes: [HEAD=absent EXPECT==37]
    <automated>grep -c '^## Review findings' .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-SUMMARY.md</automated>
    SUMMARY records the findings: [HEAD=absent EXPECT==1]
    <automated>grep -c -i -F -f <(sed '/^ *$/d' docs/internal/gate-forbidden.txt) .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-SUMMARY.md</automated>
    SUMMARY holds no FORBID entry: [HEAD=absent EXPECT==0]
    <automated>grep -h -E '(^|[^A-Za-z])[A-Za-z]:/' .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-SUMMARY.md .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-checks.py | wc -l</automated>
    No drive-letter path in SUMMARY or CHECKS: [HEAD=absent EXPECT==0]
    <automated>find docs/internal/base-ljr docs/internal/base-k6x docs/internal/presentation/backup-261123 -newer .planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-PLAN.md | wc -l</automated>
    BASE, base-k6x and backup-261123 untouched since this plan was written: [HEAD=0 EXPECT==0 GUARD MUTATION: any write there makes a file newer than PLAN, count 1 or more]
    <automated>git diff --cached --quiet; echo $?</automated>
    Nothing staged: [HEAD=0 EXPECT==0 GUARD MUTATION: any `git add` makes it print 1]
  </verify>
  <done>
    Every finding in FINDINGS is fixed or rejected with a reason in SUMMARY. GATE prints 37 OK and `RESULT: PASS`. SUMMARY has Decisions, Section map, New facts, T1, Slide map, T2, Review findings, Render check and Gate, contains no FORBID entry and no personal path, and its status is complete. BASE, base-k6x and backup-261123 are untouched; nothing is staged or committed. The orchestrator's render re-check is the last step.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| internal pages -> public repo | CHECKS, PLAN and SUMMARY will be committed to a public repo; the two pages and FINDINGS hold internal content and stay in gitignored `docs/internal/` |
| executor -> Docker container | CHECKS and ASM run in `python:3.12-slim` with the repo mounted |
| gitignored pages -> no version history | a bad edit to DD, SD or SRC cannot be undone with git; BASE is the only undo copy |
| orchestrator render server -> network | the render check serves the presentation folder over HTTP |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-q-ljr-01 | Information disclosure | CHECKS, SUMMARY, PLAN | high | mitigate | Forbidden literals reach the reused fpj check only through env GATE_FORBIDDEN; new checks print check names, counts, ids, positions and number tokens, never page text; SUMMARY describes content by topic; FINDINGS (which may quote page text) lives in gitignored WORK; T1 and T3 grep CHECKS and SUMMARY against FORBID and for drive-letter paths (expect 0) |
| T-q-ljr-02 | Tampering | DD, SD (data loss) | high | mitigate | T1 confirms both pages equal BASE before any edit; BASE, base-k6x and backup-261123 are never edited (T3 `find -newer` guard); DD is rebuilt from SRC, so SRC is the single deep-dive source |
| T-q-ljr-03 | Tampering | facts in DD and SD | high | mitigate | dd-numbers (no number absent from BASE_DD), deck-numbers (no deck number absent from DD), svg-identical, code-paths existence, new non-numeric facts only with a repo pointer listed in SUMMARY, fact-check reviewer with mandatory fix of altered or unsupported claims |
| T-q-ljr-04 | Repudiation | commits | medium | mitigate | No `git add` or commit by the executor; T1 checks CHECKS is untracked, T3 checks nothing is staged |
| T-q-ljr-05 | Information disclosure | render HTTP server | medium | mitigate | Server bound to 127.0.0.1 only, folder mounted read-only, container removed with `docker stop` after the check |
| T-q-ljr-06 | Elevation of privilege | scripts in Docker | low | accept | Stdlib-only scripts written in this task, no network use, no package installs |
| T-q-ljr-SC | Tampering | npm/pip/cargo installs | low | accept | No package installs and no image pulls; `python:3.12-slim` is already local; the render check uses the orchestrator's browser tools, not a pulled browser image |
</threat_model>

<verification>
After T3 and the orchestrator's render re-check, from the repository root in Git Bash:
- GATE prints 37 OK lines and `RESULT: PASS`, exit 0.
- The render re-check passes at 1440 and 390 on both pages (or SUMMARY records which step could not run).
- `git status --short` shows CHECKS, SUMMARY and this PLAN untracked, `.planning/config.json` and `.planning/STATE.md` as before, and no file under `docs/internal/`.
- No app or test file changed, so `./run-unit-tests.sh` is not run.
</verification>

<success_criteria>
- A newcomer reads the deep dive top to bottom from Livello 1 to Livello 5; an engineer or a manager jumps straight to a level or to the costs, risks and decision checklist from the TOC or the intro line.
- The deep dive is about 40% of its former length and states no fact the base did not state (or a repo source does not state).
- The deck walks the same levels with the same titles and terms, and every fact on it is in the deep dive.
- GATE passes on both files, every earlier rule included; the render check passes; every reviewer finding has a recorded resolution; nothing is committed until the user's OK.
</success_criteria>

<output>
Create `.planning/quick/261123-ljr-rewrite-deep-dive-to-guides-zero-to-prod/261123-ljr-SUMMARY.md` (started in T1). It holds "## Decisions", "## Section map", "## New facts", "## T1", "## Slide map", "## T2", "## Review findings", "## Render check" and "## Gate". The quick orchestrator updates STATE.md and, after the user's OK, commits PLAN, SUMMARY, CHECKS and STATE.md.
</output>
