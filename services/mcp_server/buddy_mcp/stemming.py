"""Italian text normalisation and stemming for the in-memory handbook index (D-02).

Page text and query go through the same functions, so case and accents fold identically on
both sides. Phase 5 Recall@5 validates this choice (stems, no prefix matching).
"""

import re
import unicodedata
from typing import Final

import snowballstemmer

_STEMMER: Final = snowballstemmer.stemmer("italian")
_TOKEN: Final = re.compile(r"\w+")

# Already accent-stripped: stopwords are compared after normalize(), before stemming.
# Domain words (ferie, permessi, malattia) are deliberately absent.
ITALIAN_STOPWORDS: Final[frozenset[str]] = frozenset(
    {
        "il", "lo", "la", "i", "gli", "le", "un", "uno", "una",
        "di", "a", "da", "in", "con", "su", "per", "tra", "fra",
        "e", "ed", "o", "ma", "che", "chi", "cui", "non",
        "come", "dove", "quando", "quale", "quali", "quanto",
        "mi", "ti", "si", "ci", "vi",
        "del", "dello", "della", "dei", "degli", "delle",
        "al", "allo", "alla", "ai", "agli", "alle",
        "dal", "dalla", "nel", "nella", "nei", "sul", "sulla",
        "sono", "ho", "ha", "posso", "puo", "perche",
    }
)  # fmt: skip


def normalize(text: str) -> str:
    """Lowercase, decompose (NFKD) and drop combining marks, so `CITTÀ` equals `citta`."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(normalize(text))


def stem_text(text: str) -> list[str]:
    """Normalised, Snowball-stemmed tokens of `text` (stopwords kept)."""
    tokens = _tokens(text)
    return list(_STEMMER.stemWords(tokens)) if tokens else []


def stem_query(query: str) -> list[str]:
    """Like stem_text, with Italian stopwords dropped before stemming."""
    tokens = [token for token in _tokens(query) if token not in ITALIAN_STOPWORDS]
    return list(_STEMMER.stemWords(tokens)) if tokens else []
