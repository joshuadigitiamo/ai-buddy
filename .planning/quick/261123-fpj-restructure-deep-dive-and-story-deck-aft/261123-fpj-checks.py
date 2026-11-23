"""Gate for the two internal HTML decks.

Run in Docker, from the repository root (Git Bash)::

    GATE_FORBIDDEN="$(cat docs/internal/gate-forbidden.txt)" MSYS_NO_PATHCONV=1 \\
    docker run --rm -v "$PWD:/w" -w /w -e GATE_FORBIDDEN python:3.12-slim \\
    python -I <this file> docs/internal/presentation/deep-dive.html \\
    docs/internal/presentation/story-deck.html

Environment:
    GATE_FORBIDDEN: forbidden literals, one per line. The list is kept outside the
        repository, so no forbidden text is committed with this script. Several
        literals contain a comma, so the separator is a newline, not a comma.

Output: one line ``OK|FAIL <check> <file> -- <detail>`` per check and file, then
``RESULT: PASS`` or ``RESULT: FAIL``. Exit code 0 only if every check is OK.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

Result = tuple[bool, str]

BACKUP_DIR = "backup-261123"
CLICKUP_ID = re.compile(r"[a-z0-9]{5}-\d{5}")
SVG_BLOCK = re.compile(r"<svg\b.*?</svg>", re.S)
OLD_CODES = re.compile(r"\b(?:ROLL|CONT|NUDGE|OPS|LLM|RET)-0\d\b|\bD-?\d{1,2}a?\b")
BOT_GATE_TERMS = re.compile(
    r"gate (di |delle |sulle |su )?citazion|gate del bot|gate nel codice|controlli del gate",
    re.I,
)
PART_TITLES = (("parte-a", "Per la direzione"), ("parte-b", "Come funziona"), ("parte-c", "Appendice"))


def _strip_comments(text: str) -> str:
    """Removes HTML comments."""
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def _visible_text(text: str) -> str:
    """Removes style, script, comments and tags, leaving the text a reader sees."""
    text = re.sub(r"<(style|script)\b.*?</\1>", "", text, flags=re.S | re.I)
    return re.sub(r"<[^>]+>", " ", _strip_comments(text))


def _element_start(raw: str, element_id: str) -> int:
    """Returns the offset of the opening tag with the given id, or -1."""
    match = re.search(rf'<[a-z0-9]+\b[^>]*\bid="{re.escape(element_id)}"', raw)
    return match.start() if match else -1


def _element_text(raw: str, element_id: str) -> str | None:
    """Returns the inner text of the element with the given id, or None if it is missing."""
    start = _element_start(raw, element_id)
    if start < 0:
        return None
    tag = re.match(r"<([a-z0-9]+)", raw[start:]).group(1)  # type: ignore[union-attr]
    end = raw.find(f"</{tag}>", start)
    return re.sub(r"<[^>]+>", "", raw[start : end if end > 0 else len(raw)])


def check_forbidden(raw: str, _path: Path) -> Result:
    """Fails if a literal from GATE_FORBIDDEN is present; names it by position only."""
    entries = [e.strip() for e in os.environ.get("GATE_FORBIDDEN", "").split("\n") if e.strip()]
    if not entries:
        return False, "GATE_FORBIDDEN empty"
    low = raw.lower()
    hits = [(i, low.count(e.lower())) for i, e in enumerate(entries, 1) if e.lower() in low]
    if hits:
        return False, "entries " + ", ".join(f"#{i} x{n}" for i, n in hits)
    return True, f"{len(entries)} entries, no hit"


def check_clickup(raw: str, _path: Path) -> Result:
    """Fails on any ClickUp-style id."""
    hits = CLICKUP_ID.findall(raw)
    return (not hits), f"{len(hits)} match(es)"


def check_svg_count(raw: str, _path: Path) -> Result:
    """Requires exactly 4 SVG openings and 4 closings."""
    opens, closes = len(re.findall(r"<svg\b", raw)), raw.count("</svg>")
    return opens == 4 and closes == 4, f"{opens} open, {closes} close"


def _svg_skeletons(raw: str) -> list[str]:
    """Returns each SVG block with label text and whitespace between tags dropped."""
    raw = raw.replace("\r\n", "\n")
    return [re.sub(r">[^<]*<", "><", block) for block in SVG_BLOCK.findall(raw)]


def check_svg_geometry(raw: str, path: Path) -> Result:
    """Compares SVG markup, minus label text, with the backup copy."""
    backup = path.parent / BACKUP_DIR / path.name
    if not backup.is_file():
        return False, f"backup missing: {BACKUP_DIR}/{path.name}"
    old = _svg_skeletons(backup.read_bytes().decode("utf-8"))
    new = _svg_skeletons(raw)
    if len(old) != len(new):
        return False, f"{len(new)} svg vs {len(old)} in backup"
    for pos, (a, b) in enumerate(zip(old, new), 1):
        if a != b:
            return False, f"svg #{pos} differs from backup"
    return True, f"{len(new)} svg identical to backup"


def check_unique_ids(raw: str, _path: Path) -> Result:
    """Requires every id attribute value to occur once."""
    ids = re.findall(r'(?<![\w-])id="([^"]*)"', raw)
    dups = sorted({i for i in ids if ids.count(i) > 1})
    return (not dups), (f"duplicates: {dups[:5]}" if dups else f"{len(ids)} ids unique")


def check_anchors(raw: str, _path: Path) -> Result:
    """Requires every #href to resolve and every section id to have a link."""
    ids = set(re.findall(r'(?<![\w-])id="([^"]*)"', raw))
    hrefs = set(re.findall(r'href="#([^"]*)"', raw))
    sections = set(re.findall(r'<section\b[^>]*\bid="([^"]*)"', raw))
    broken, orphan = sorted(hrefs - ids), sorted(sections - hrefs)
    ok = not broken and not orphan
    return ok, f"broken {broken[:5]}, unlinked {orphan[:5]}" if not ok else f"{len(hrefs)} links ok"


def check_section_balance(raw: str, _path: Path) -> Result:
    """Requires equal counts of section openings and closings."""
    opens, closes = len(re.findall(r"<section\b", raw)), raw.count("</section>")
    return opens == closes, f"{opens} open, {closes} close"


def check_bot_terms(raw: str, _path: Path) -> Result:
    """Fails if the bot's runtime check is called a gate."""
    text = _strip_comments(raw)
    found = BOT_GATE_TERMS.findall(text)
    wf = text.find('id="wf-')
    if wf < 0:
        return False, "no bot workflow diagram"
    starts = [m for m in re.finditer(r'<section\b|<div class="stage">', text[:wf])]
    if not starts:
        return False, "no container before the bot workflow diagram"
    start = starts[-1]
    if start.group().startswith("<section"):
        end = text.find("</section>", start.start())
    else:
        end = text.find('<div class="stage">', start.end())
    block = text[start.start() : end if end > 0 else len(text)]
    block = re.sub(r"gate della Milestone", "", block, flags=re.I)
    inner = len(re.findall("gate", block, re.I))
    ok = not found and inner == 0
    return ok, f"{len(found)} bot-gate phrase(s), {inner} 'gate' in the bot section"


def check_parts(raw: str, _path: Path) -> Result:
    """Requires the three part headings, in order, with their titles."""
    positions = []
    for element_id, title in PART_TITLES:
        start, text = _element_start(raw, element_id), _element_text(raw, element_id)
        if start < 0 or text is None or title not in text:
            return False, f"{element_id} missing or without '{title}'"
        positions.append(start)
    ordered = positions == sorted(positions)
    return ordered, "three parts in order" if ordered else "parts out of order"


def _old_codes(raw: str, begin: str | None, end: str) -> Result:
    """Lists old internal codes in the visible text between two part markers."""
    s = 0 if begin is None else _element_start(raw, begin)
    e = _element_start(raw, end)
    if s < 0 or e < 0:
        return False, "part id missing"
    full = [m.group(0) for m in OLD_CODES.finditer(_visible_text(raw[s:e]))]
    return (not full), (f"{len(full)} code(s): {sorted(set(full))[:8]}" if full else "none")


def check_old_codes_a(raw: str, _path: Path) -> Result:
    """No old codes from the file start to Parte B."""
    return _old_codes(raw, None, "parte-b")


def check_old_codes_b(raw: str, _path: Path) -> Result:
    """No old codes in Parte B."""
    return _old_codes(raw, "parte-b", "parte-c")


COMMON = (
    ("forbidden-strings", check_forbidden),
    ("clickup-ids", check_clickup),
    ("svg-count", check_svg_count),
    ("svg-geometry", check_svg_geometry),
    ("unique-ids", check_unique_ids),
    ("anchors", check_anchors),
    ("section-balance", check_section_balance),
    ("bot-terms", check_bot_terms),
)
DEEP_DIVE_ONLY = (
    ("parts", check_parts),
    ("old-codes-a", check_old_codes_a),
    ("old-codes-b", check_old_codes_b),
)


def main(argv: list[str]) -> int:
    """Runs every check on every file in argv and prints one line per check."""
    if not argv:
        print("usage: checks.py FILE [FILE ...]", file=sys.stderr)
        return 2
    failed = False
    for name in argv:
        path = Path(name)
        raw = path.read_bytes().decode("utf-8")
        checks = COMMON + (DEEP_DIVE_ONLY if "deep-dive" in path.name else ())
        for label, check in checks:
            ok, detail = check(raw, path)
            failed |= not ok
            print(f"{'OK' if ok else 'FAIL'} {label} {name} -- {detail}")
    print("RESULT: FAIL" if failed else "RESULT: PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
