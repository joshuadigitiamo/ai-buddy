"""Gate for the two internal HTML decks after the rewrite to the Guides level structure.

Reuses the eight common checks of the earlier deck gate (261123-fpj) and the planning-terms
check of 261123-k6x, then adds four common checks (``svg-identical``, ``svg-markers``,
``code-paths``, ``old-refs``), seven deep-dive checks and four deck checks. The deep dive
prints 20 lines, the deck 17.

Run in Docker, from the repository root (Git Bash)::

    GATE_FORBIDDEN="$(cat docs/internal/gate-forbidden.txt)" MSYS_NO_PATHCONV=1 \\
    docker run --rm -v "$PWD:/w" -w /w -e GATE_FORBIDDEN python:3.12-slim \\
    python -I <this file> docs/internal/presentation/deep-dive.html \\
    docs/internal/presentation/story-deck.html

Environment:
    GATE_FORBIDDEN: forbidden literals, one per line, read by the reused fpj check. The list
        lives outside the repository, so no forbidden text is committed with this script.

BASE: ``<parent of the page's directory>/base-ljr/<file name>`` holds the state before the
rewrite. ``svg-identical`` and ``dd-numbers`` compare against it.

NOT_REPO_PATHS: maps a ``<code>`` span that names something outside this repository to the
reason it is skipped by ``code-paths``. Add an entry only with such a reason.

Output: ``OK|FAIL <check> <file> -- <detail>`` per check, then ``RESULT: PASS|FAIL``. The new
checks print check names, counts, ids, positions and number tokens, never page text.
"""

from __future__ import annotations

import html
import importlib.util
import os
import re
import sys
from pathlib import Path
from types import ModuleType

Result = tuple[bool, str]

QUICK = Path(__file__).resolve().parent.parent
BASE_DIR = "base-ljr"
NUM = re.compile(r"\d+(?:[.,/]\d+)*")
DATE = re.compile(r"\d{2}/\d{2}/\d{4}")
WORDS_MIN, WORDS_MAX = 5000, 7000
MAX_SLIDES = 14
LEVELS = (
    ("livello-1", "Livello 1 — Base"),
    ("livello-2", "Livello 2 — Intermedio"),
    ("livello-3", "Livello 3 — Avanzato"),
    ("livello-4", "Livello 4 — Produzione"),
    ("livello-5", "Livello 5 — Ecosistema e scelte"),
    ("riferimento", "Best practice e riferimento"),
)
CLOSING = (
    "Errori comuni",
    "Checklist delle decisioni",
    "Casi d'uso reali",
    "Riferimento rapido",
    "Il quadro d'insieme",
    "Fonti",
)
TARGET = re.compile(
    r'<h2 class="part" id="(livello-[1-5]|riferimento)">(.*?)</h2>'
    r'|<section id="(s\d+)">\s*<h2>(.*?)</h2>',
    re.S,
)
PATH_SPAN = re.compile(r"[\w.-]+(?:/[\w.{}<>*-]+)+/?")
FILE_SPAN = re.compile(r"[\w.-]+\.(?:md|sh|py|ya?ml|toml|txt|lock|json)")
SKIP_DIRS = {".git", ".venv", ".planning", ".idea", ".ruff_cache", "__pycache__", "node_modules"}
NOT_REPO_PATHS: dict[str, str] = {
    "GUIDES_INDEX.md": "file of the Guides repository, outside this repository",
    "vllm/vllm-openai": "container image name, not a path",
}


def _load(folder: str, name: str, alias: str) -> ModuleType:
    """Loads an earlier gate from its file, whose name is not an importable identifier.

    Args:
        folder: quick-task folder name under ``.planning/quick``.
        name: gate file name.
        alias: module name to register.

    Returns:
        The executed module.
    """
    spec = importlib.util.spec_from_file_location(alias, QUICK / folder / name)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fpj = _load("261123-fpj-restructure-deep-dive-and-story-deck-aft", "261123-fpj-checks.py", "fpj")
k6x = _load("261123-k6x-remove-planning-process-references-from-", "261123-k6x-checks.py", "k6x")


def _lf(text: str) -> str:
    """Normalises CRLF to LF."""
    return text.replace("\r\n", "\n")


def _visible(text: str) -> str:
    """Returns the unescaped text a reader sees, SVG text included."""
    return html.unescape(fpj._visible_text(text))


def _visible_no_svg(text: str) -> str:
    """Returns the unescaped visible text with every SVG block removed."""
    return _visible(fpj.SVG_BLOCK.sub(" ", text))


def _norm(fragment: str) -> str:
    """Strips tags, unescapes, collapses whitespace and maps U+2019 to an ASCII apostrophe."""
    plain = html.unescape(re.sub(r"<[^>]+>", "", fragment))
    return " ".join(plain.split()).replace("’", "'")


def _base_text(path: Path) -> str | None:
    """Returns the LF-normalised base copy of a page, or None if it is missing."""
    base = path.parent.parent / BASE_DIR / path.name
    return _lf(base.read_bytes().decode("utf-8")) if base.is_file() else None


def _targets(raw: str) -> list[tuple[str, str]]:
    """Returns (id, normalised heading text) of every divider and section, in order."""
    return [(m.group(1) or m.group(3), _norm(m.group(2) or m.group(4))) for m in TARGET.finditer(raw)]


def _is_divider(target_id: str) -> bool:
    """Tells a level divider id from a section id."""
    return target_id.startswith("livello-") or target_id == "riferimento"


def _sections(raw: str) -> list[tuple[str, str]]:
    """Returns (id, heading text) of every numbered section, in order."""
    return [t for t in _targets(raw) if not _is_divider(t[0])]


def _bare_title(heading: str) -> str:
    """Drops the leading ``N. `` of a section heading."""
    return re.sub(r"^\d+\.\s*", "", heading)


def _repo_file_names() -> set[str]:
    """Returns every file name in the repository, outside the skipped directories."""
    names: set[str] = set()
    for dirpath, dirs, files in os.walk("."):
        here = Path(dirpath).as_posix()
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and f"{here}/{d}" != "./docs/internal"]
        names.update(files)
    return names


def check_planning_terms(raw: str, path: Path) -> Result:
    """Fails on a planning term; delegates to the k6x check.

    Args:
        raw: page text.
        path: page path.

    Returns:
        (ok, detail).
    """
    return k6x.check_planning_terms(raw, path)


def check_svg_identical(raw: str, path: Path) -> Result:
    """Requires the SVG blocks to equal those of the base, in order.

    Args:
        raw: page text.
        path: page path.

    Returns:
        (ok, detail).
    """
    base = _base_text(path)
    if base is None:
        return False, "base missing"
    old, new = fpj.SVG_BLOCK.findall(base), fpj.SVG_BLOCK.findall(raw)
    for pos, (a, b) in enumerate(zip(old, new), 1):
        if a != b:
            return False, f"svg #{pos} differs from base"
    return len(old) == len(new), f"{len(new)} svg vs {len(old)} in base" if len(old) != len(new) else f"{len(new)} svg identical to base"


def check_svg_markers(raw: str, _path: Path) -> Result:
    """Requires one marker-id prefix per SVG, distinct across SVGs, and local url() references.

    Args:
        raw: page text.
        _path: page path, unused.

    Returns:
        (ok, detail).
    """
    seen: dict[str, int] = {}
    for number, block in enumerate(fpj.SVG_BLOCK.findall(raw), 1):
        ids = set(re.findall(r'(?<![\w-])id="([^"]+)"', block))
        prefixes = {m.split("-")[0] for m in re.findall(r'<marker\b[^>]*\bid="([^"]+)"', block)}
        if len(prefixes) > 1:
            return False, f"svg #{number} mixes marker prefixes"
        for prefix in prefixes:
            if prefix in seen:
                return False, f"svg #{number} reuses the marker prefix of svg #{seen[prefix]}"
            seen[prefix] = number
        missing = sorted(set(re.findall(r"url\(#([^)]+)\)", block)) - ids)
        if missing:
            return False, f"svg #{number} references {len(missing)} id(s) it does not define"
    return True, f"{len(seen)} marker prefixes, all references local"


def check_code_paths(raw: str, _path: Path) -> Result:
    """Requires every path-like or file-name-like ``<code>`` span to exist in the repository.

    Args:
        raw: page text.
        _path: page path, unused.

    Returns:
        (ok, detail).
    """
    spans = re.findall(r"<code\b[^>]*>(.*?)</code>", fpj._strip_comments(fpj.SVG_BLOCK.sub(" ", raw)), re.S)
    names: set[str] | None = None
    bad: list[str] = []
    for span in spans:
        text = html.unescape(re.sub(r"<[^>]+>", "", span)).strip()
        if ":" in text or text in NOT_REPO_PATHS:
            continue
        if PATH_SPAN.fullmatch(text):
            if text.startswith((".planning", "docs/internal")) or not Path(text).exists():
                bad.append(text)
        elif FILE_SPAN.fullmatch(text):
            names = _repo_file_names() if names is None else names
            if text not in names:
                bad.append(text)
    return (not bad), (f"missing: {sorted(set(bad))[:8]}" if bad else f"{len(spans)} spans checked")


def check_old_refs(raw: str, _path: Path) -> Result:
    """Fails on a reference to the old A/B/C structure in the visible text outside SVG.

    Args:
        raw: page text.
        _path: page path, unused.

    Returns:
        (ok, detail).
    """
    text = _visible_no_svg(raw)
    counts = {
        "part": len(re.findall(r"Parte [ABC]\b", text)),
        "section-code": len(re.findall(r"\b[ABC]\d{1,2}\b", text)),
        "old-code": len(fpj.OLD_CODES.findall(text)),
    }
    detail = ", ".join(f"{k} x{v}" for k, v in counts.items())
    return not any(counts.values()), detail


def check_toc(raw: str, _path: Path) -> Result:
    """Requires the TOC links to equal the dividers and sections, in text and order.

    Args:
        raw: page text.
        _path: page path, unused.

    Returns:
        (ok, detail).
    """
    nav = re.search(r'<nav class="toc"[^>]*>(.*?)</nav>', raw, re.S)
    if nav is None:
        return False, "no toc nav"
    links = [(m.group(1), _norm(m.group(2))) for m in re.finditer(r'<a href="#([^"]+)">(.*?)</a>', nav.group(1), re.S)]
    targets = _targets(raw)
    if links == targets:
        return True, f"{len(links)} links match their targets"
    for pos, (a, b) in enumerate(zip(links, targets), 1):
        if a != b:
            same = "text differs" if a[0] == b[0] else f"link {a[0]} vs target {b[0]}"
            return False, f"position {pos}: {same}"
    return False, f"{len(links)} links vs {len(targets)} targets"


def check_levels(raw: str, _path: Path) -> Result:
    """Requires the six dividers, sections under each, and the six closing sections in order.

    Args:
        raw: page text.
        _path: page path, unused.

    Returns:
        (ok, detail).
    """
    if re.search(r'id="parte-[abc]"', raw):
        return False, "an old part id is still present"
    pos, since, closing = 0, 0, []
    for target_id, text in _targets(raw):
        if _is_divider(target_id):
            if pos and since == 0:
                return False, f"no section after divider #{pos}"
            if pos >= len(LEVELS) or (target_id, text) != LEVELS[pos]:
                return False, f"divider #{pos + 1} differs from the contract"
            pos, since = pos + 1, 0
        else:
            if pos == 0:
                return False, "a section precedes the first divider"
            since += 1
            if pos == len(LEVELS):
                closing.append(_bare_title(text))
    if pos != len(LEVELS):
        return False, f"{pos} dividers, expected {len(LEVELS)}"
    if len(closing) != len(CLOSING):
        return False, f"{len(closing)} closing sections, expected {len(CLOSING)}"
    for number, (title, prefix) in enumerate(zip(closing, CLOSING), 1):
        if not title.startswith(prefix):
            return False, f"closing section #{number} does not start with the contract title"
    return True, f"{len(LEVELS)} dividers, {len(CLOSING)} closing sections in order"


def check_section_numbers(raw: str, _path: Path) -> Result:
    """Requires section k to have id ``sk`` and a heading starting ``k. ``, k = 1..N.

    Args:
        raw: page text.
        _path: page path, unused.

    Returns:
        (ok, detail).
    """
    sections = _sections(raw)
    for k, (section_id, text) in enumerate(sections, 1):
        if section_id != f"s{k}" or not text.startswith(f"{k}. "):
            return False, f"section #{k}: id {section_id} or heading number out of sequence"
    return bool(sections), f"{len(sections)} sections numbered 1..{len(sections)}"


def check_word_count(raw: str, _path: Path) -> Result:
    """Requires the visible words outside SVG to stay in the target range.

    Args:
        raw: page text.
        _path: page path, unused.

    Returns:
        (ok, detail with the total and the counts per part).
    """
    total = len(_visible_no_svg(raw).split())
    cuts = [m.start() for m in re.finditer(r'<h2 class="part" id="(?:livello-[1-5]|riferimento)"', raw)]
    bounds = [0, *cuts, len(raw)]
    labels = ["front", "L1", "L2", "L3", "L4", "L5", "ref"]
    parts = [len(_visible_no_svg(raw[a:b]).split()) for a, b in zip(bounds, bounds[1:])]
    detail = f"{total} words; " + ", ".join(f"{k} {v}" for k, v in zip(labels, parts))
    return WORDS_MIN <= total <= WORDS_MAX, detail


def check_dd_numbers(raw: str, path: Path) -> Result:
    """Requires every number token of the page to exist in the base page.

    Section-number prefixes, internal link texts and ``Livello N`` are removed first.

    Args:
        raw: page text.
        path: page path.

    Returns:
        (ok, detail listing the new tokens).
    """
    base = _base_text(path)
    if base is None:
        return False, "base missing"
    text = re.sub(r'<a href="#s\d+">.*?</a>', " ", raw, flags=re.S)
    text = re.sub(r'(<section id="s\d+">\s*<h2>)\d+\. ', r"\1", text)
    text = re.sub(r"Livello [1-5]", " ", text)
    extra = sorted(set(NUM.findall(_visible(text))) - set(NUM.findall(_visible(base))))
    return (not extra), (f"new tokens: {extra[:20]}" if extra else "no new number token")


def check_title_block(raw: str, _path: Path) -> Result:
    """Requires the title, subtitle, date-only numbers and three section links in the header.

    Args:
        raw: page text.
        _path: page path, unused.

    Returns:
        (ok, detail).
    """
    head = re.search(r"<header>(.*?)</header>", raw, re.S)
    if head is None:
        return False, "no header"
    inner = head.group(1)
    h1 = re.search(r"<h1>(.*?)</h1>", inner, re.S)
    if h1 is None or _norm(h1.group(1)) != "AI Buddy — Guida completa":
        return False, "h1 differs from the contract"
    if "Da zero alla produzione" not in _norm(inner):
        return False, "subtitle missing"
    bad = [t for t in NUM.findall(_visible(inner)) if not DATE.fullmatch(t)]
    if bad:
        return False, f"{len(bad)} non-date number token(s) in the header"
    hrefs = re.findall(r'href="#(s\d+)"', inner)
    titles = dict(_sections(raw))
    if len(hrefs) < 3 or not any(_bare_title(titles.get(h, "")).startswith("Checklist delle decisioni") for h in hrefs):
        return False, f"{len(hrefs)} section link(s), checklist link missing or fewer than three"
    return True, f"{len(hrefs)} section links, dates only"


def check_conventions(raw: str, _path: Path) -> Result:
    """Requires at least five «In breve» boxes and six trade-off notes.

    Args:
        raw: page text.
        _path: page path, unused.

    Returns:
        (ok, detail).
    """
    boxes = raw.count("<h3>In breve</h3>")
    text = html.unescape(raw)
    notes = text.count("<strong>Quando non serve") + text.count("<strong>Quando è eccessivo")
    return boxes >= 5 and notes >= 6, f"{boxes} «In breve» boxes (min 5), {notes} trade-off notes (min 6)"


def check_slides(raw: str, _path: Path) -> Result:
    """Requires at most 14 slides, numbered 01..N in order.

    Args:
        raw: page text.
        _path: page path, unused.

    Returns:
        (ok, detail).
    """
    stages = raw.count('<div class="stage">')
    nums = re.findall(r'<span class="num">(\d+)</span>', raw)
    ok = 1 <= stages <= MAX_SLIDES and nums == [f"{i:02d}" for i in range(1, stages + 1)]
    return ok, f"{stages} slides (max {MAX_SLIDES}), {len(nums)} num spans"


def check_title_slide(raw: str, _path: Path) -> Result:
    """Requires the title slide to hold no number except dates.

    Args:
        raw: page text.
        _path: page path, unused.

    Returns:
        (ok, detail).
    """
    parts = raw.split('<div class="stage">')
    if len(parts) < 2:
        return False, "no slide"
    first = re.sub(r'<span class="num">.*?</span>', " ", parts[1], flags=re.S)
    first = first.split("<!--")[0]
    bad = [t for t in NUM.findall(_visible(first)) if not DATE.fullmatch(t)]
    return (not bad), (f"{len(bad)} non-date number token(s)" if bad else "dates only")


def check_deck_numbers(raw: str, path: Path) -> Result:
    """Requires every number token of the deck to exist in the deep dive.

    Slide numbers and card numbers (``num`` and ``n`` spans) are ignored.

    Args:
        raw: page text.
        path: deck path; the deep dive is its sibling ``deep-dive.html``.

    Returns:
        (ok, detail listing the missing tokens).
    """
    dive = path.with_name("deep-dive.html")
    if not dive.is_file():
        return False, "deep dive missing"
    text = re.sub(r'<span class="(?:num|n)">.*?</span>', " ", raw, flags=re.S)
    missing = sorted(set(NUM.findall(_visible(text))) - set(NUM.findall(_visible(_lf(dive.read_bytes().decode("utf-8"))))))
    return (not missing), (f"missing from the deep dive: {missing[:20]}" if missing else "every token exists in the deep dive")


def check_deck_kickers(raw: str, path: Path) -> Result:
    """Requires each kicker after the first to name a deep-dive section of the stated level.

    Args:
        raw: page text.
        path: deck path; the deep dive is its sibling ``deep-dive.html``.

    Returns:
        (ok, detail naming the slide number and the reason).
    """
    dive = path.with_name("deep-dive.html")
    if not dive.is_file():
        return False, "deep dive missing"
    sections: list[tuple[int, str]] = []
    level = 0
    for target_id, text in _targets(_lf(dive.read_bytes().decode("utf-8"))):
        if _is_divider(target_id):
            level = 6 if target_id == "riferimento" else int(target_id[-1])
        else:
            sections.append((level, _bare_title(text)))
    kickers = [_norm(k) for k in re.findall(r'<p class="kicker">(.*?)</p>', raw, re.S)]
    if len(kickers) != raw.count('<div class="stage">'):
        return False, f"{len(kickers)} kickers for {raw.count('<div class=\"stage\">')} slides"
    previous = 0
    for number, kicker in enumerate(kickers[1:], 2):
        m = re.fullmatch(r"(?:Livello ([1-5])|Riferimento) · (.+)", kicker)
        if m is None:
            return False, f"slide {number}: kicker has no level prefix"
        wanted = int(m.group(1)) if m.group(1) else 6
        rest = m.group(2)
        if not any(lv == wanted and (rest == t or rest.startswith(t + " · ")) for lv, t in sections):
            return False, f"slide {number}: no section of that level carries this title"
        if wanted < previous:
            return False, f"slide {number}: level goes back"
        previous = wanted
    return True, f"{len(kickers) - 1} kickers match deep-dive sections, levels non-decreasing"


COMMON = fpj.COMMON + (
    ("planning-terms", check_planning_terms),
    ("svg-identical", check_svg_identical),
    ("svg-markers", check_svg_markers),
    ("code-paths", check_code_paths),
    ("old-refs", check_old_refs),
)
DEEP_DIVE_ONLY = (
    ("toc", check_toc),
    ("levels", check_levels),
    ("section-numbers", check_section_numbers),
    ("word-count", check_word_count),
    ("dd-numbers", check_dd_numbers),
    ("title-block", check_title_block),
    ("conventions", check_conventions),
)
DECK_ONLY = (
    ("slides", check_slides),
    ("title-slide", check_title_slide),
    ("deck-numbers", check_deck_numbers),
    ("deck-kickers", check_deck_kickers),
)


def main(argv: list[str]) -> int:
    """Runs the common checks plus the deep-dive or deck group on every file in argv.

    The fpj main is not reused because it has no deck-only group.

    Args:
        argv: page paths; a file name containing ``deep-dive`` gets the deep-dive group.

    Returns:
        0 if every check is OK, 1 if one fails, 2 on a usage error.
    """
    if not argv:
        print("usage: checks.py FILE [FILE ...]", file=sys.stderr)
        return 2
    failed = False
    for name in argv:
        path = Path(name)
        raw = _lf(path.read_bytes().decode("utf-8"))
        group = DEEP_DIVE_ONLY if "deep-dive" in path.name else DECK_ONLY
        for label, check in COMMON + group:
            ok, detail = check(raw, path)
            failed |= not ok
            print(f"{'OK' if ok else 'FAIL'} {label} {name} -- {detail}")
    print("RESULT: FAIL" if failed else "RESULT: PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
