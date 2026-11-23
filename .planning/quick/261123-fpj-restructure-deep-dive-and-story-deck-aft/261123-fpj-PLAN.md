---
phase: quick-261123-fpj
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-checks.py
  - .planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-SUMMARY.md
  - docs/internal/presentation/deep-dive.html
  - docs/internal/presentation/story-deck.html
  - docs/internal/presentation/backup-261123/
  - docs/internal/gate-forbidden.txt
autonomous: true
requirements: [quick-261123-fpj]

estimate:
  tokens: 240000
  raw_tokens: 240000
  tasks: 3
  confidence: low

must_haves:
  truths:
    - "The deep dive opens with a short lede and an «In breve» box, then has three parts: Parte A for the direction (plain language), Parte B for the tech team (glossary first), Parte C as an appendix with the September research"
    - "Parte A holds one decisions table, one costs table, a ranked risks list with an owner per risk, and a numbered list of next steps, as spec section 1 describes"
    - "Every terminology, fact and clear-writing item of spec sections 2, 3 and 4 is applied to the deep dive; the story deck carries the same facts and terms per spec section 5, with no other restructure"
    - "The four SVG diagrams in each file keep their geometry; only text labels change, and only where spec section 2 or 3 requires it"
    - "The gate script exits 0 on both decks: no GATE_FORBIDDEN string, no internal ids, no old codes in Parte A or B, no bot check called a gate"
    - "No committed file (gate script, PLAN, SUMMARY) contains a name, handbook content, an internal id, a gate result number or a fact detail from the spec"
  artifacts:
    - path: .planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-checks.py
      provides: "Stdlib gate for the two decks; forbidden literals come only from env GATE_FORBIDDEN"
    - path: docs/internal/presentation/deep-dive.html
      provides: "Deep dive in three parts (gitignored, never committed)"
    - path: docs/internal/presentation/story-deck.html
      provides: "Story deck with the same facts and terms (gitignored, never committed)"
    - path: docs/internal/presentation/backup-261123/
      provides: "Copies of both decks as they were before this task; the svg-geometry check compares against them"
    - path: .planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-SUMMARY.md
      provides: "Record of the earlier edits of 2026-11-23, what changed per part, and the gate output"
  key_links:
    - from: docs/internal/gate-forbidden.txt
      to: .planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-checks.py
      via: "shell reads the gitignored file into env GATE_FORBIDDEN; docker passes it with -e GATE_FORBIDDEN"
      pattern: 'os.environ.get\("GATE_FORBIDDEN"'
    - from: .planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-checks.py
      to: docs/internal/presentation/backup-261123/
      via: "svg-geometry check reads <dir of FILE>/backup-261123/<basename of FILE>"
      pattern: "backup-261123"
    - from: "deep-dive.html TOC links"
      to: "deep-dive.html section ids a1..a7, b1..b12, c1..c7"
      via: "anchors check: every href=\"#x\" resolves and every section id has a TOC link"
      pattern: 'href="#'
---

<objective>
Restructure the internal deep dive into three parts and apply the four reviewers' fixes to the deep dive and the story deck. Record the earlier deck edits of 2026-11-23 in SUMMARY.

Purpose: the reviewers found the deep dive hard to read for the direction (decisions, costs and risks are scattered), inconsistent in terms, and wrong on some facts. The story deck repeats some of those facts and terms.

Output: a stdlib gate script (committed), the two restructured decks (gitignored, never committed), backups of both decks, and SUMMARY.md.

Source of every content change: the internal fix spec `deck-fix-spec.md` (session scratchpad; the orchestrator gives the absolute path) (below: SPEC). SPEC is INTERNAL. Never copy its facts, names, numbers or quotes into the gate script, SUMMARY or any other committed file.

Coverage (every SPEC part has a task):

| SPEC part | Task |
|-----------|------|
| Header hard rules (roles only, be general, no internal ids, SVG geometry untouched, keep `.dd-fig` CSS) | T1 gate checks; T2 and T3 edits |
| §1 structure | T1 moves sections and adds part headings; T2 writes header, «In breve», Parte A, Parte C, footer; T3 writes Parte B |
| §2 terminology | T2 (header, Parte A, Parte C, footer); T3 (Parte B, SVG labels, story deck) |
| §3 facts 1-16 | T2 for the parts it owns; T3 for Parte B and the story deck |
| §4 clear writing | T2 and T3, each on the parts it owns |
| §5 story deck | T3 |
| §6 gate script | T1 |
| Earlier edits of 2026-11-23 (planning context) | T1 starts SUMMARY with them |

Execution is SEQUENTIAL on the main working tree. Do not use worktrees: they would not contain the gitignored decks.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md

Paths used below:
- SPEC: the absolute scratchpad path in the objective. Read it whole before T1.
- CW: `~/.claude/skills/clear-writing/SKILL.md` (93 lines) and `~/.claude/skills/clear-writing/references/italian.md` (75 lines). Read both from disk with the Read tool before writing any Italian prose (T2, T3).
- PYSTD: `~/.claude/setup/PYTHON_DOCSTRING_COMMENT_STANDARD.md`. Read it before writing the gate script (T1).
- CHECKS: `.planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-checks.py`
- SUMMARY: `.planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-SUMMARY.md`
- DD: `docs/internal/presentation/deep-dive.html` (1750 lines, 162 KB, CRLF line endings, 23 sections s1..s23, 4 SVG diagrams)
- SD: `docs/internal/presentation/story-deck.html` (972 lines, 76 KB, 14 slides as `<div class="stage">`, 4 SVG diagrams)
- BK: `docs/internal/presentation/backup-261123/` (created in T1)
- FORBID: `docs/internal/gate-forbidden.txt` (created in T1; gitignored, like all of `docs/internal/`)

## How to run CHECKS (GATE)

Use the Bash tool (Git Bash), cwd at the repository root:

`GATE_FORBIDDEN="$(cat docs/internal/gate-forbidden.txt)" MSYS_NO_PATHCONV=1 docker run --rm -v "$PWD:/w" -w /w -e GATE_FORBIDDEN python:3.12-slim python -I .planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-checks.py docs/internal/presentation/deep-dive.html docs/internal/presentation/story-deck.html`

Below, "GATE" means this full command. `MSYS_NO_PATHCONV=1` is required in Git Bash: without it, Docker fails with "the working directory 'W:/' is invalid" (tested at planning time). The `python:3.12-slim` image is already local. The command is Bash syntax; it does not work in PowerShell.

GATE prints one line per check and file, `OK <check> <file> -- <detail>` or `FAIL <check> <file> -- <detail>`, then `RESULT: PASS` or `RESULT: FAIL`. It exits 0 only if every check is OK.

Expected GATE outcome per stage (computed from the current files at planning time):
- Before T1's restructure: OK for forbidden-strings, clickup-ids, svg-count, svg-geometry, unique-ids, anchors and section-balance on both files; FAIL for bot-terms (both files), parts, old-codes-a and old-codes-b (deep dive). The current deep dive has 39 old-code matches in visible text and 18 numeric cross-references of the form «sezione NN».
- After T1: parts OK; bot-terms, old-codes-a and old-codes-b still FAIL.
- After T2: old-codes-a OK on the deep dive.
- After T3: every check OK, `RESULT: PASS`.

If a check FAILs on a part you own, fix the deck text. Never edit CHECKS after T1's commit to make a check pass. If a check looks wrong, stop and report it.

## Rules for every deck edit

- Hard rules from the SPEC header apply everywhere: roles only, never a person's name; general wording, never exact gate results or counts that reveal them (thresholds are allowed); no internal ids, personal paths or client names.
- SVG diagrams (ids prefixed `arch-`, `dep-`, `loc-`, `wf-`; 4 per file): change only the text inside `<text>`, `<title>` and `<desc>`, and only where SPEC §2 or §3 changes the term or fact shown. Never change tags, attributes, coordinates or comments inside an `<svg>`. Keep the `.dd-fig` CSS rules.
- Never Read DD whole. Use Grep to find line numbers (`<section id=`, `<svg`, `</svg>`), then Read text ranges with offset/limit. Skip the SVG line ranges unless you change a label.
- Take each Edit `old_string` from a Read of the raw HTML, entities included.
- Language: Italian. Apply all CW rules and run the CW check list on every sentence you write or change.
- DD and SD are gitignored: they get no commits. BK is the only copy of their state before this task. Keep BK until the user has reviewed the decks.
- If context runs short, finish the current task, run GATE, append the task's notes to SUMMARY, and stop. A fresh executor continues from the next task (re-read SPEC and CW first).

## Repo hygiene

- Stage only the file a task names (`git add <path>`); never `git add -A` or `git add .`.
- Never read `.env`.
- Commit message format: `docs(quick-261123-fpj): ...`, ending with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- The quick orchestrator commits PLAN, SUMMARY and STATE.md after T3. The executor commits only CHECKS (T1).
</context>

<tasks>

<task type="tracer">
  <name>Task 1: Tracer: gate script, backups and the three-part skeleton of the deep dive</name>
  <files>.planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-checks.py, .planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-SUMMARY.md, docs/internal/presentation/deep-dive.html, docs/internal/presentation/backup-261123/, docs/internal/gate-forbidden.txt</files>
  <read_first>
    - SPEC (whole file)
    - PYSTD and CW SKILL.md (for the script's docstrings and comments)
    - .planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/ (empty except this PLAN)
    - DD lines 139-172 (header and TOC) and one section opening (lines 173-176) to see the `snum` span format «NN · Label»
  </read_first>
  <behavior>
    CHECKS (stdlib only, Python 3.12, type hints, Google docstrings per PYSTD) takes one or more file paths. Every check below runs on every file, except the three marked "deep dive only" (file basename contains `deep-dive`):
    - forbidden-strings: entries = env GATE_FORBIDDEN split on commas, each stripped, empties dropped. No entries -> FAIL with detail "GATE_FORBIDDEN empty". Any entry found in the raw file, case-insensitive -> FAIL. The detail names the entry by its position (1-based) and the hit count, never the entry text.
    - clickup-ids: regex `[a-z0-9]{5}-\d{5}` on the raw file -> FAIL on any match.
    - svg-count: count of `<svg` and count of `</svg>` must both be 4.
    - svg-geometry: reads `<dir of FILE>/backup-261123/<basename of FILE>`; missing -> FAIL. Extracts every `<svg ...>...</svg>` block from both copies (LF-normalised), replaces every `>[^<]*<` with `><` (drops label text and whitespace), and requires the two lists to be equal. The detail names the first differing SVG by position.
    - unique-ids: every `id="..."` value (not preceded by a word character or `-`, so `data-id` and `aria-*` do not count) occurs once.
    - anchors: every `href="#x"` resolves to an `id="x"` in the same file, and every `<section id="x">` has a matching `href="#x"`.
    - section-balance: count of `<section` (word boundary) equals count of `</section>`.
    - bot-terms: on the file with HTML comments removed: (1) no match, case-insensitive, of `gate (di |delle |sulle |su )?citazion|gate del bot|gate nel codice|controlli del gate`; (2) the container of the bot workflow diagram (the last `<section` or `<div class="stage">` opening before the first `id="wf-`, up to the next `</section>` for a section, or up to the next `<div class="stage">` or end of file for a slide) contains no "gate", case-insensitive, after removing every "gate della Milestone", case-insensitive. No `id="wf-` -> FAIL.
    - parts (deep dive only): elements with `id="parte-a"`, `id="parte-b"`, `id="parte-c"` exist in this order, and the text of each element up to its closing tag contains «Per la direzione», «Come funziona», «Appendice» respectively.
    - old-codes-a and old-codes-b (deep dive only): regex `\b(?:ROLL|CONT|NUDGE|OPS|LLM|RET)-0\d\b|\bD-?\d{1,2}a?\b` on visible text (style, script, comments and tags removed). Scope a: from the file start to the `parte-b` element. Scope b: from the `parte-b` element to the `parte-c` element. Missing part ids -> FAIL. The detail lists the matched codes.
    Output: one line per check and file in the form `OK <check> <file> -- <detail>` or `FAIL <check> <file> -- <detail>`; last line `RESULT: PASS` or `RESULT: FAIL`; exit 0 if all OK, else 1.
  </behavior>
  <action>
    Per SPEC §6 and the SPEC header rules:
    1. Back up both decks before any edit: create BK and copy DD and SD into it with `cp -p`. Check that `cmp` reports both copies identical to the originals.
    2. Create FORBID as one line of comma-separated entries with no spaces around the commas: the owner's first name and surname as two separate entries (take them from `git config user.name`), then the six exact-result literals SPEC §6 lists. Confirm `git check-ignore -q docs/internal/gate-forbidden.txt` exits 0. Never print FORBID's content in chat or SUMMARY.
    3. Write CHECKS with the Write tool, implementing the behavior block exactly. The script must hold no literal from FORBID: it hard-codes only the generic regexes and the part titles listed above. Module docstring: purpose, the GATE command, and the env var.
    4. Run GATE on the unchanged decks. Compare the output with "Expected GATE outcome per stage" (before restructure). Run the two mutation checks listed in verify. If a check disagrees with the expected outcome, fix CHECKS now, before the commit.
    5. Restructure DD into the three parts with a throwaway stdlib script saved as `docs/internal/presentation/backup-261123/restructure.py` (gitignored) and run in Docker with the GATE mount (`python:3.12-slim`, `MSYS_NO_PATHCONV=1`). Move whole sections; never retype SVG markup. The script must:
       a. read and write DD with `newline=""`, so the CRLF line endings stay;
       b. split DD into: the part before the TOC `<nav`, the TOC, the 23 `<section id="sN">...</section>` blocks, and the part from `<footer>` to the end. Assert exactly 23 sections with ids s1..s23, each once, and only whitespace between them; on a failed assertion, stop without writing;
       c. reorder and rename per SPEC §1 with this map (old id -> new id; the `snum` code is the new id in capitals, replacing the «NN» in «NN · Label»): Parte A: s1->a1, s2->a2, s21->a6, s22->a7 (a3, a4 and a5 are written in T2). Parte B: s3->b1, s4->b2, s10->b3, s11->b4, s12->b5, s13->b6, s14->b7, s15->b8, s16->b9, s19->b10, s20->b11, s23->b12. Parte C: s5->c1, s6->c2, s7->c3, s8->c4, s9->c5, s17->c6, s18->c7;
       d. insert one part heading before the first section of each part: `<h2 class="part" id="parte-a">Parte A · Per la direzione</h2>`, `id="parte-b"` with «Parte B · Come funziona», `id="parte-c"` with «Parte C · Appendice: ricerca di settembre». Add one `.part` rule to the existing `<style>` so a part heading stands apart from section headings. Do not touch the `.dd-fig` rules;
       e. rewrite every numeric cross-reference «sezione NN» / «sezioni NN» (two digits) to the new code through the map, for example «sezione B7». Leave «sezione 2.1» in the footer alone: it points to another document;
       f. rebuild the TOC as three groups, one per part, each with the part title and an `<ol>` of links `href="#<new id>"`, with label text taken from the `snum` label after the code;
       g. assert after writing: 23 `<section` openings, 4 `<svg` openings.
    6. Run GATE again: parts, svg-geometry, anchors and the other structural checks must be OK on DD (see verify).
    7. Create SUMMARY with: (a) "## Earlier edits of 2026-11-23 (recorded, no rework)": both decks rewritten from the plan to what was built and measured; four inline SVG diagrams (architecture, cloud deployment, local kind, bot workflow) made with the diagram-design skill and embedded only in the decks; the owner's name removed; exact gate results replaced by general wording at the user's request; a read-only review by four reviewers (clear writing, technical reader, management reader, fact check), run with plain agents and not with GSD, per the user's rule; (b) "## T1": the GATE output before and after the restructure (OK/FAIL lines only; they hold no internal content). Write SUMMARY in English and in general terms. Never quote SPEC.
    8. Commit only CHECKS: `git add .planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-checks.py`, message `docs(quick-261123-fpj): add gate script for the internal decks`.
  </action>
  <verify>
    <automated>test -s docs/internal/presentation/backup-261123/deep-dive.html && cmp docs/internal/presentation/backup-261123/story-deck.html docs/internal/presentation/story-deck.html && git check-ignore -q docs/internal/gate-forbidden.txt && echo present</automated>
    Prints present (BK and FORBID do not exist at HEAD): [HEAD=absent EXPECT==present]
    <automated>MSYS_NO_PATHCONV=1 GATE_FORBIDDEN="AI Buddy" docker run --rm -v "$PWD:/w" -w /w -e GATE_FORBIDDEN python:3.12-slim python -I .planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-checks.py docs/internal/presentation/deep-dive.html docs/internal/presentation/story-deck.html | grep '^FAIL forbidden-strings ' | grep -vc 'AI Buddy'</automated>
    Mutation: a string present in both decks makes forbidden-strings FAIL on both files, and the detail does not echo it (CHECKS does not exist at HEAD): [HEAD=absent EXPECT==2]
    <automated>MSYS_NO_PATHCONV=1 GATE_FORBIDDEN=x docker run --rm -v "$PWD:/w" -w /w -e GATE_FORBIDDEN python:3.12-slim sh -c 'mkdir -p /tmp/m && sed "0,/<\/svg>/s/<\/svg>//" docs/internal/presentation/story-deck.html > /tmp/m/story-deck.html && python -I .planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-checks.py /tmp/m/story-deck.html' | grep -c '^FAIL svg-count '</automated>
    Mutation: one `</svg>` removed makes svg-count FAIL: [HEAD=absent EXPECT==1]
    <automated>GATE_FORBIDDEN="$(cat docs/internal/gate-forbidden.txt)" MSYS_NO_PATHCONV=1 docker run --rm -v "$PWD:/w" -w /w -e GATE_FORBIDDEN python:3.12-slim python -I .planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-checks.py docs/internal/presentation/deep-dive.html docs/internal/presentation/story-deck.html | grep -E '^OK (forbidden-strings|clickup-ids|svg-count|svg-geometry|unique-ids|anchors|section-balance|parts) ' | wc -l</automated>
    Structural checks OK after the restructure (7 generic checks x 2 files + parts on DD; 14 before the restructure): [HEAD=absent EXPECT==15]
    <automated>grep -o -E 'sezion[ei] [0-9]{2}' docs/internal/presentation/deep-dive.html | wc -l</automated>
    Numeric cross-references: [HEAD=18 EXPECT==0]
    <automated>grep -o '<section' docs/internal/presentation/deep-dive.html | wc -l</automated>
    Section count (regression guard for the move): [HEAD=23 EXPECT==23 GUARD MUTATION: a restructure that drops or duplicates one section makes the count 22 or 24]
    <automated>grep -c -i -F -f <(tr ',' '\n' < docs/internal/gate-forbidden.txt | sed '/^ *$/d') .planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-checks.py</automated>
    CHECKS holds no FORBID entry: [HEAD=absent EXPECT==0]
    <automated>files=$(git show --name-only --format= HEAD) && printf '%s\n' "$files" | grep -c .</automated>
    The T1 commit holds one file, CHECKS: [HEAD=6 EXPECT==1]
  </verify>
  <done>
    BK holds both original decks. FORBID exists and is gitignored. CHECKS is committed alone and contains no FORBID entry. Both mutation checks FAIL as expected. After the restructure, DD has 23 sections in three parts with ids a1, a2, a6, a7, b1..b12, c1..c7, a TOC in three groups, no numeric cross-references, and byte-identical SVG geometry. GATE shows the 15 structural OK lines. SUMMARY holds the earlier-edits record and the T1 GATE output.
  </done>
</task>

<task type="auto">
  <name>Task 2: Deep dive: header, «In breve», Parte A, Parte C and footer</name>
  <files>docs/internal/presentation/deep-dive.html, .planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-SUMMARY.md</files>
  <read_first>
    - CW: SKILL.md and references/italian.md, whole, from disk
    - SPEC §1 (Parte A, Parte C, footer), §2, §3, §4, and the header rules
    - DD: header and TOC, sections a1, a2, a6, a7 and c1..c7 (find their line ranges with Grep on `<section id=`), and the cost and licence passages in b1 and b9 that A3 and A4 draw on
  </read_first>
  <action>
    Write in Italian, per CW and the SPEC header rules. This task owns: the header (eyebrow and lede), the «In breve» box, the TOC entries of Parte A, sections a1..a7, sections c1..c7, and the footer.
    1. Header and «In breve» (SPEC §1): shorten the lede. Add the «In breve» box right after `</header>` and before the TOC, using the existing `callout note` class. It answers four points in general wording: what the assistant is, whether it works, who uses it today, and what is missing before a second user.
    2. Parte A in plain language, with no infrastructure jargon (SPEC §1 A1-A7):
       a. a1 and a2: rewrite from the moved sections as SPEC A1 and A2 say. A short version of the end-to-end example may go in a2 (SPEC leaves this to you; record your choice in SUMMARY).
       b. Write three new sections between a2 and a6: `<section id="a3">` «A3 · Cosa deve decidere la direzione» (one table with the four columns and the rows SPEC A3 lists; the most urgent row first, as SPEC A3 says); `<section id="a4">` «A4 · Costi» (one table, today vs rollout, a total range, and the unknowns named explicitly, per SPEC A4); `<section id="a5">` «A5 · Rischi» (a ranked list, each risk with who handles it, per SPEC A5). Copy the markup pattern of the existing sections (`snum` span, `h2`, `tblwrap` for tables). Add the three TOC links to the Parte A group.
       c. a6: a numbered list of next steps per SPEC A6, with no ordering claim that SPEC A6 says is unrecorded. a7: adapt per SPEC A7, and make every count in a7 match the a6 list.
    3. Parte C (SPEC §1 Parte C): mark the part as background research from September at its start. In c4, keep the licence detail; the urgent item now leads A3. In c5, resolve the contradiction that SPEC §3 item 16 names for that section. In c6, add the GPU and model-serving glossary terms SPEC §1 names, with their definitions taken from b1 (T3 removes them from b1).
    4. Footer: state the sources in general terms, per SPEC §1 Footer. No file paths, research numbers or internal ids.
    5. In every part this task owns, apply SPEC §2 (one name per concept; «gate» only for the milestone acceptance test; the phase wording; old internal codes removed or said in words, with at most a small legend in Parte C; acronyms spelled out at first use in each part), every SPEC §3 item whose fact appears in this text, and SPEC §4 (agent visible, no sentences that defend the work, ordered steps as numbered lists, failure paths stated, calques replaced, referents named). For each SPEC §3 item, Grep DD for its key terms, so no occurrence in a1..a7, c1..c7, the header or the footer is missed.
    6. Run GATE. Fix every FAIL of forbidden-strings, clickup-ids, svg-count, svg-geometry, unique-ids, anchors, section-balance, parts and old-codes-a on DD. bot-terms and old-codes-b stay for T3.
    7. Append "## T2" to SUMMARY: per part, what changed, in general terms (for example "Parte A: new sections for decisions, costs and risks"); the SPEC §3 item numbers applied (numbers only, no content); the a2 choice; the GATE lines for DD. Never quote SPEC.
  </action>
  <verify>
    <automated>GATE_FORBIDDEN="$(cat docs/internal/gate-forbidden.txt)" MSYS_NO_PATHCONV=1 docker run --rm -v "$PWD:/w" -w /w -e GATE_FORBIDDEN python:3.12-slim python -I .planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-checks.py docs/internal/presentation/deep-dive.html docs/internal/presentation/story-deck.html | grep -E '^OK (forbidden-strings|clickup-ids|svg-count|svg-geometry|unique-ids|anchors|section-balance|parts|old-codes-a) docs/internal/presentation/deep-dive.html' | wc -l</automated>
    DD checks owned so far all OK (8 after T1): [HEAD=absent EXPECT==9]
    <automated>grep -o -E 'id="a[1-7]"' docs/internal/presentation/deep-dive.html | sort -u | wc -l</automated>
    Parte A section ids (4 after T1): [HEAD=0 EXPECT==7]
    <automated>grep -c 'In breve' docs/internal/presentation/deep-dive.html</automated>
    «In breve» box: [HEAD=0 EXPECT>=1]
    <automated>grep -c 'Cosa deve decidere la direzione' docs/internal/presentation/deep-dive.html</automated>
    Decisions section A3: [HEAD=0 EXPECT>=1]
    <automated>grep -c "in quest'ordine" docs/internal/presentation/deep-dive.html</automated>
    Ordering claim gone from a6: [HEAD=1 EXPECT==0]
  </verify>
  <done>
    DD has the «In breve» box after the header, Parte A with sections a1..a7 (decisions table, one costs table, ranked risks with owners, numbered next steps whose count matches a7), Parte C marked as September background, and a general footer. GATE shows the 9 DD checks above OK. SUMMARY "## T2" lists the changes per part and the SPEC §3 item numbers applied.
  </done>
</task>

<task type="auto">
  <name>Task 3: Deep dive Parte B, SVG labels, story deck, final gate on both files</name>
  <files>docs/internal/presentation/deep-dive.html, docs/internal/presentation/story-deck.html, .planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-SUMMARY.md</files>
  <read_first>
    - CW: SKILL.md and references/italian.md, if this task runs in a fresh context
    - SPEC §1 (Parte B), §2, §3, §4, §5, and the header rules
    - SUMMARY "## T2" (which SPEC §3 items T2 already applied)
    - DD sections b1..b12 (Grep `<section id="b` for line ranges; skip SVG ranges except the labels you change)
    - SD slides 4, 5, 7, 10, 11, 13 and 14 (Grep `class="kicker"` for line numbers; Read with offset/limit)
  </read_first>
  <action>
    Write in Italian, per CW and the SPEC header rules. This task owns sections b1..b12 of DD, the SVG labels of both files, and SD.
    1. b1 glossary (SPEC §1 Parte B): keep only the terms Parte B uses, plus the entries SPEC §1 lists for it. Remove the GPU and model-serving terms that T2 moved to c6. Correct the entries that SPEC §3 changes.
    2. b2..b12: apply SPEC §2, every SPEC §3 item whose fact appears in Parte B, and SPEC §4. In b7 (the bot section), call the bot's runtime check «controllo delle citazioni» everywhere, headings included; «gate» may appear there only as «gate della Milestone». Write the ordered steps as numbered lists (index update, bot steps, the six checks, CI steps). State the failure paths SPEC §4 names. Rename b12's heading per SPEC §4. Spell out acronyms at their first use in Parte B.
    3. SVG labels in both files (SPEC §2 and §3): in the bot workflow diagram, rename the decision label, the six-checks annotation and the legend from the gate term to «Controllo» / «controlli», per SPEC §2. In the architecture diagram, rename the label that calls the bot check a gate. Update the `<title>` and `<desc>` sentences that use the gate term for the bot check. Change any other label only where a SPEC §3 fact changes what it shows. Never touch tags, attributes or coordinates (svg-geometry).
    4. SD (SPEC §5): apply the slide changes SPEC §5 lists (slides 05, 11, 13, 14; keep slide 07's milestone gate). Give every SD sentence that states a fact or term that SPEC §2 or §3 corrects the same correction as DD, including the next-steps slide's ordering claim that SPEC §1 A6 removes. Make no other restructure: same 14 slides, same order.
    5. Run GATE on both files. Fix every FAIL in the text. The final output must end with `RESULT: PASS`.
    6. Append to SUMMARY: "## T3" (what changed in Parte B, which SVG labels changed and why, which SD slides changed, the SPEC §3 item numbers applied; general terms only, never SPEC content), and "## Gate" with the final GATE output (OK lines and `RESULT: PASS`). Note that BK keeps the pre-task copies until the user reviews the decks. Then run the SUMMARY hygiene check in verify.
  </action>
  <verify>
    <automated>GATE_FORBIDDEN="$(cat docs/internal/gate-forbidden.txt)" MSYS_NO_PATHCONV=1 docker run --rm -v "$PWD:/w" -w /w -e GATE_FORBIDDEN python:3.12-slim python -I .planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-checks.py docs/internal/presentation/deep-dive.html docs/internal/presentation/story-deck.html | tail -n 1 | grep -c '^RESULT: PASS$'</automated>
    Final gate on both files ends with RESULT: PASS (after T2 it still ends with RESULT: FAIL on bot-terms and old-codes-b): [HEAD=absent EXPECT==1]
    <automated>grep -c 'La lista onesta' docs/internal/presentation/deep-dive.html</automated>
    b12 heading renamed: [HEAD=1 EXPECT==0]
    <automated>grep -c "in quest'ordine" docs/internal/presentation/story-deck.html</automated>
    SD ordering claim gone: [HEAD=1 EXPECT==0]
    <automated>grep -c 'controllo delle citazioni' docs/internal/presentation/story-deck.html</automated>
    SD names the bot check: [HEAD=0 EXPECT>=1]
    <automated>grep -c -i -F -f <(tr ',' '\n' < docs/internal/gate-forbidden.txt | sed '/^ *$/d') .planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-SUMMARY.md</automated>
    SUMMARY holds no FORBID entry (SUMMARY does not exist at HEAD): [HEAD=absent EXPECT==0]
  </verify>
  <done>
    GATE prints `RESULT: PASS` for both files: no FORBID string, no internal ids, 4 SVGs per file with unchanged geometry, unique ids, resolving anchors, three parts, no old codes in Parte A or B, and no bot check called a gate. SD has the same 14 slides with the SPEC §5 changes. SUMMARY has "## Earlier edits", "## T1", "## T2", "## T3" and "## Gate", and contains no FORBID entry.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| internal decks -> public repo | CHECKS, PLAN and SUMMARY are committed to a public repo; the decks and SPEC hold internal content |
| executor -> Docker container | CHECKS and the throwaway restructure script run in `python:3.12-slim` with the repo mounted |
| gitignored decks -> no version history | an edit that breaks DD or SD cannot be undone with git |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-q-fpj-01 | Information disclosure | CHECKS, SUMMARY (committed) | high | mitigate | Forbidden literals live only in gitignored FORBID and reach CHECKS through env GATE_FORBIDDEN; CHECKS reports a hit by entry position, never the text; T1 and T3 grep CHECKS and SUMMARY against FORBID (expect 0); SUMMARY uses general terms and SPEC §3 item numbers only |
| T-q-fpj-02 | Tampering | DD restructure (data loss) | high | mitigate | BK copies taken before any edit and checked with `cmp`; the restructure script asserts 23 sections and whitespace-only gaps before it writes; svg-geometry compares every SVG with BK |
| T-q-fpj-03 | Tampering | facts in DD and SD | medium | mitigate | Every content change traces to a SPEC section; GATE checks names, result literals, internal ids, old codes and bot-check terms |
| T-q-fpj-04 | Elevation of privilege | scripts run in Docker | low | accept | Stdlib-only scripts written in this task, no network use, no package installs |
| T-q-fpj-SC | Tampering | npm/pip/cargo installs | low | accept | No package installs; `python:3.12-slim` is already local |
</threat_model>

<verification>
After T3, from the repository root in Git Bash:
- GATE prints `RESULT: PASS` and exits 0.
- `git status --short` shows no tracked deck file and no file under `docs/internal/`; `git log --oneline -1 -- .planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-checks.py` shows the T1 commit.
- `ls docs/internal/presentation/backup-261123/` lists deep-dive.html, story-deck.html and restructure.py.
- No app or test file changed, so `./run-unit-tests.sh` is not run.
</verification>

<success_criteria>
- DD reads as three parts: the direction finds decisions, costs, risks and next steps in Parte A without reading Parte B or C.
- DD and SD state the same facts and use the same terms, as SPEC sections 2, 3 and 5 require.
- GATE passes on both files; the SVG geometry equals the backups.
- No committed file holds internal content; SUMMARY records the earlier edits of 2026-11-23 and the gate output.
</success_criteria>

<output>
Create `.planning/quick/261123-fpj-restructure-deep-dive-and-story-deck-aft/261123-fpj-SUMMARY.md` (started in T1). It holds the sections "## Earlier edits of 2026-11-23 (recorded, no rework)", "## T1", "## T2", "## T3" and "## Gate". The quick orchestrator updates STATE.md and commits PLAN, SUMMARY and STATE.md.
</output>
