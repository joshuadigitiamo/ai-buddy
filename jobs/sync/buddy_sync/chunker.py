"""Heading-based Markdown chunker for the Guides (D-20).

``heading_outline`` is the only heading parser in the sync job: the chunker and the
``GUIDES_INDEX.md`` generator both use it, so they cannot disagree about what a heading is.
Parsing goes through markdown-it, so heading-like lines inside fenced code are body text.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final

from markdown_it import MarkdownIt
from markdown_it.token import Token

from buddy_core.models import GuideChunk, make_chunk_key

PIPELINE_VERSION: Final[str] = "1"
MAX_CHUNK_CHARS: Final[int] = 6000


@dataclass(frozen=True, slots=True)
class Heading:
    """A ``##`` or ``###`` heading; ``line`` is 1-based."""

    level: int
    title: str
    line: int


@dataclass(frozen=True, slots=True)
class _Block:
    """A top-level block of the document; both bounds are 0-based, ``end`` exclusive."""

    start: int
    end: int


def _normalized_lines(text: str) -> list[str]:
    """Split like markdown-it does (CRLF and CR become LF), so token maps index these lines."""
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _top_level_tokens(text: str) -> list[Token]:
    """Block tokens at nesting level 0 that open or are self-contained, each with a line map."""
    tokens = MarkdownIt().parse(text)
    return [t for t in tokens if t.level == 0 and t.nesting >= 0 and t.map is not None]


def _heading_tag(token: Token) -> str | None:
    return token.tag if token.type == "heading_open" and token.tag in ("h2", "h3") else None


def heading_outline(text: str) -> list[Heading]:
    """Every ``##`` and ``###`` heading with its 1-based line, in document order."""
    tokens = MarkdownIt().parse(text)
    outline: list[Heading] = []
    for index, token in enumerate(tokens):
        if token.level != 0 or token.map is None or _heading_tag(token) is None:
            continue
        inline = tokens[index + 1]
        outline.append(Heading(int(token.tag[1]), inline.content.strip(), token.map[0] + 1))
    return outline


def assign_chunk_keys(file: str, chunks: Sequence[GuideChunk]) -> list[GuideChunk]:
    """Recompute every chunk key in order; identical heading keys get an occurrence suffix."""
    seen: Counter[str] = Counter()
    keyed: list[GuideChunk] = []
    for chunk in chunks:
        base = make_chunk_key(file, chunk.h2, chunk.h3, chunk.part_index)
        seen[base] += 1
        key = make_chunk_key(file, chunk.h2, chunk.h3, chunk.part_index, seen[base])
        keyed.append(replace(chunk, chunk_key=key))
    return keyed


def _slice_text(lines: Sequence[str], start: int, end: int) -> tuple[str, int]:
    """Source lines [start, end) minus trailing blanks; returns the text and its last line."""
    while end > start and not lines[end - 1].strip():
        end -= 1
    return "\n".join(lines[start:end]).rstrip(), end


def _section_chunks(
    lines: Sequence[str],
    *,
    file: str,
    h2: Heading,
    h3: Heading | None,
    blocks: Sequence[_Block],
) -> list[GuideChunk]:
    if not blocks:
        return []
    heading_line = (h3 or h2).line
    text, last_line = _slice_text(lines, blocks[0].start, blocks[-1].end)
    if not text:
        return []
    return [
        GuideChunk(
            chunk_key="",
            file=file,
            h2=h2.title,
            h3=h3.title if h3 else None,
            heading=(h3 or h2).title,
            line_start=heading_line,
            line_end=last_line,
            part_index=0,
            text=text,
        )
    ]


def chunk_markdown(text: str, *, file: str, max_chars: int = MAX_CHUNK_CHARS) -> list[GuideChunk]:
    """Split one guide into chunks: one per ``###``, with its parent ``##`` title (D-20).

    Text above the first ``##`` is not indexed. A ``##`` without ``###`` is one chunk; prose
    between a ``##`` and its first ``###`` is a preamble chunk with ``h3`` None.
    """
    lines = _normalized_lines(text)
    tokens = _top_level_tokens(text)
    outline = heading_outline(text)
    headings_by_line = {h.line: h for h in outline}

    chunks: list[GuideChunk] = []
    h2: Heading | None = None
    h3: Heading | None = None
    blocks: list[_Block] = []

    def flush() -> None:
        if h2 is not None:
            chunks.extend(_section_chunks(lines, file=file, h2=h2, h3=h3, blocks=blocks))

    for token in tokens:
        assert token.map is not None
        heading = headings_by_line.get(token.map[0] + 1) if _heading_tag(token) else None
        if heading is not None:
            flush()
            blocks = []
            if heading.level == 2:
                h2, h3 = heading, None
            else:
                h3 = heading
            continue
        if h2 is not None:
            blocks.append(_Block(token.map[0], token.map[1]))
    flush()
    return assign_chunk_keys(file, chunks)
