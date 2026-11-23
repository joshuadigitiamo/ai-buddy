"""Gate for the two internal HTML decks: no planning-process references, no fact changes.

Reuses every check of the earlier deck gate (261123-fpj) and adds five:
``planning-terms``, ``svg-vs-base``, ``code-spans``, ``structure``, ``numbers``.

Run in Docker, from the repository root (Git Bash)::

    GATE_FORBIDDEN="$(cat docs/internal/gate-forbidden.txt)" MSYS_NO_PATHCONV=1 \\
    docker run --rm -v "$PWD:/w" -w /w -e GATE_FORBIDDEN python:3.12-slim \\
    python -I <this file> docs/internal/presentation/deep-dive.html \\
    docs/internal/presentation/story-deck.html

Environment:
    GATE_FORBIDDEN: forbidden literals, one per line, read by the reused fpj check.
        The list lives outside the repository, so no forbidden text is committed here.

Base copies: ``<parent of the deck's directory>/base-k6x/<deck file name>`` hold the state
before the rewrite. The new checks compare the decks against them.

Allowlist rule: ``NUMBER_ALLOWLIST`` maps a number token to the reason it may disappear.
Add an entry only for a number lost together with a planning-process reference that the
phase-bound strip does not cover. Never allowlist a fact number.

Output and exit code are those of the fpj gate. The new checks print category names,
counts and positions, never deck text; the ``numbers`` failure detail prints number tokens.
"""

from __future__ import annotations

import html
import importlib.util
import re
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType

Result = tuple[bool, str]

FPJ_PATH = (
    Path(__file__).resolve().parent.parent
    / "261123-fpj-restructure-deep-dive-and-story-deck-aft"
    / "261123-fpj-checks.py"
)
BASE_DIR = "base-k6x"
NUMBER_ALLOWLIST: dict[str, str] = {}

PLANNING_TERMS = {
    "phase": re.compile(r"\bfas[ei]\b|\bphases?\b", re.I),
    "milestone": re.compile(r"\bmilestones?\b", re.I),
    "planning-path": re.compile(r"\.planning\b", re.I),
    "gsd": re.compile(r"\bgsd\b", re.I),
    "phase-file": re.compile(
        r"-(?:NOTES|UAT|VERIFICATION|SUMMARY|CONTEXT|PLAN|RESEARCH|GAP-DECISION"
        r"|VALIDATION|DISCOVERY)\.md\b"
    ),
    "decision-id": re.compile(r"\bD-?\d{1,2}\b"),
    "requirement-id": re.compile(r"\b[A-Z]{2,6}-\d{2}\b"),
}
GATE_WORD = re.compile(r"\bgate\b", re.I)
CODE_SPAN = re.compile(r"<code\b[^>]*>.*?</code>", re.S)
PHASE_BOUND_NUMBER = re.compile(r"\b(?:fas[ei]|phases?|milestones?)\s+\d+[a-z]?\b", re.I)
NUMBER_TOKEN = re.compile(r"\d+(?:[.,/]\d+)*")


def _load_fpj() -> ModuleType:
    """Loads the fpj gate module from its file, whose name is not an importable identifier.

    Returns:
        The executed fpj module.
    """
    spec = importlib.util.spec_from_file_location("fpj_checks", FPJ_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fpj = _load_fpj()


def _lf(text: str) -> str:
    """Normalises CRLF to LF."""
    return text.replace("\r\n", "\n")


def _base(path: Path) -> str | None:
    """Returns the LF-normalised base copy of a deck, or None if it is missing."""
    base = path.parent.parent / BASE_DIR / path.name
    return _lf(base.read_bytes().decode("utf-8")) if base.is_file() else None


def _term_hits(text: str) -> Counter[str]:
    """Counts planning-term hits per category; ``gate`` ignores every ``<code>`` span."""
    hits = Counter({name: len(rx.findall(text)) for name, rx in PLANNING_TERMS.items()})
    hits["gate"] = len(GATE_WORD.findall(CODE_SPAN.sub("", text)))
    return Counter({name: n for name, n in hits.items() if n})


def _detail(hits: Counter[str]) -> str:
    """Formats category counts as ``phase x2, gate x1``."""
    return ", ".join(f"{name} x{n}" for name, n in sorted(hits.items()))


def check_planning_terms(raw: str, _path: Path) -> Result:
    """Fails on any planning term; HTML comments are ignored only inside SVG blocks."""
    scan = fpj.SVG_BLOCK.sub(lambda m: fpj._strip_comments(m.group(0)), _lf(raw))
    hits = _term_hits(scan)
    return (not hits), (_detail(hits) if hits else "none")


def check_svg_vs_base(raw: str, path: Path) -> Result:
    """Allows an SVG text node to differ from the base only if it dropped planning terms."""
    base = _base(path)
    if base is None:
        return False, "base missing"
    old, new = fpj.SVG_BLOCK.findall(base), fpj.SVG_BLOCK.findall(_lf(raw))
    if len(old) != len(new):
        return False, f"{len(new)} svg vs {len(old)} in base"
    changed = 0
    for block_no, (a, b) in enumerate(zip(old, new), 1):
        parts_a, parts_b = re.split(r"(<[^>]*>)", a), re.split(r"(<[^>]*>)", b)
        if parts_a[1::2] != parts_b[1::2]:
            return False, f"svg #{block_no} markup differs from base"
        for node_no, (ta, tb) in enumerate(zip(parts_a[0::2], parts_b[0::2]), 1):
            if ta == tb:
                continue
            if not _term_hits(ta) or _term_hits(tb):
                return False, f"svg #{block_no} text node #{node_no} changed without cause"
            changed += 1
    return True, f"{len(new)} svg, {changed} text node(s) changed"


def _span_path_error(span: str) -> str | None:
    """Returns why an added ``<code>`` span is not an existing repo-relative path, else None."""
    inner = html.unescape(re.sub(r"<[^>]+>", "", span)).strip()
    if not inner or " " in inner or inner.startswith(("/", "..")):
        return "not a relative path"
    if Path(inner).parts[0] in (".planning",) or inner.startswith("docs/internal"):
        return "points to planning or internal docs"
    if not Path(inner).exists():
        return "target missing"
    return None


def check_code_spans(raw: str, path: Path) -> Result:
    """Allows removing only ``.planning/`` spans and adding only spans naming existing paths."""
    base = _base(path)
    if base is None:
        return False, "base missing"
    old, new = set(CODE_SPAN.findall(base)), set(CODE_SPAN.findall(_lf(raw)))
    for span in sorted(old - new):
        if ".planning/" not in span:
            return False, "a code span of the base was removed or changed"
    added = []
    for span in sorted(new - old):
        error = _span_path_error(span)
        if error:
            return False, f"added code span: {error}"
        added.append(html.unescape(re.sub(r"<[^>]+>", "", span)).strip())
    return True, f"{len(new)} spans, added: {added}"


def _ids_sections_stages(text: str) -> tuple[list[str], int, int]:
    """Returns the ordered id values, the section count and the slide count."""
    return (
        re.findall(r'(?<![\w-])id="([^"]*)"', text),
        len(re.findall(r"<section\b", text)),
        text.count('class="stage"'),
    )


def check_structure(raw: str, path: Path) -> Result:
    """Requires the ordered id list, section count and slide count to equal the base."""
    base = _base(path)
    if base is None:
        return False, "base missing"
    old, new = _ids_sections_stages(base), _ids_sections_stages(_lf(raw))
    if old != new:
        return False, f"ids {len(new[0])}/{len(old[0])}, sections {new[1]}/{old[1]}, stages {new[2]}/{old[2]}"
    return True, f"{len(new[0])} ids, {new[1]} sections, {new[2]} stages equal base"


def _number_tokens(text: str) -> Counter[str]:
    """Counts number tokens in the visible text, minus phase-bound numbers."""
    visible = html.unescape(fpj._visible_text(text))
    return Counter(NUMBER_TOKEN.findall(PHASE_BOUND_NUMBER.sub("", visible)))


def check_numbers(raw: str, path: Path) -> Result:
    """Requires no lost and no new number token, except allowlisted ones."""
    base = _base(path)
    if base is None:
        return False, "base missing"
    old, new = _number_tokens(base), _number_tokens(_lf(raw))
    bad = [
        f"{tok} {old[tok]}->{new[tok]}"
        for tok in sorted(set(old) | set(new))
        if tok not in NUMBER_ALLOWLIST and (new[tok] < old[tok] or (tok not in old and new[tok]))
    ]
    if bad:
        return False, "; ".join(bad[:20])
    return True, f"{len(old)} tokens kept, 0 new"


K6X_CHECKS = (
    ("planning-terms", check_planning_terms),
    ("svg-vs-base", check_svg_vs_base),
    ("code-spans", check_code_spans),
    ("structure", check_structure),
    ("numbers", check_numbers),
)


def main(argv: list[str]) -> int:
    """Runs the fpj checks plus the k6x checks on every file in argv.

    Args:
        argv: deck file paths.

    Returns:
        0 if every check is OK, 1 if one fails, 2 on a usage error.
    """
    # fpj.main reads its module-level COMMON, so extending it reuses output and exit code.
    fpj.COMMON = fpj.COMMON + K6X_CHECKS
    return fpj.main(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
