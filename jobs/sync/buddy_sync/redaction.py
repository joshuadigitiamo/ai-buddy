"""Single redaction filter every source passes through before anything is stored.

Rules are a fixed-order table (``RULE_NAMES``). Log records carry source id, rule name and
count only, never the matched value (D-14).
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

from buddy_sync.config import SyncSettings

MASK: Final = "[REDATTO]"
REDACTION_VERSION: Final[str] = "1"

RULE_NAMES: Final[tuple[str, ...]] = (
    "image_link",
    "signed_url_query",
    "labelled_secret",
    "private_key_block",
    "token_prefix",
    "jwt",
    "iban",
    "mobile_number",
    "private_email",
    "high_entropy",
)


@dataclass(frozen=True, slots=True)
class RuleHit:
    rule: str
    count: int


@dataclass(frozen=True, slots=True)
class RedactionResult:
    text: str
    hits: tuple[RuleHit, ...]


@dataclass(frozen=True, slots=True)
class Rule:
    """One detector: a compiled pattern and a function mapping a match to its replacement."""

    name: str
    pattern: re.Pattern[str]
    replace: Callable[[re.Match[str]], str]


# Labels of credential values (IT + EN). The bare word "codice" is never a label (Pitfall 6).
# The label may be wrapped in markdown bold; everything up to the value is kept verbatim.
_LABEL_RE = re.compile(
    r"(?P<label>(?<![A-Za-z0-9])\**"
    r"(?:password|passwd|pwd|passcode|pin|codice[ \t]+di[ \t]+accesso|codice[ \t]+accesso"
    r"|codice[ \t]+sblocco|access[ \t]+code)"
    r"\**[ \t]{0,3}[:=]\**[ \t]{0,3})"
    r"(?P<value>[^\s|]{3,})",
    re.IGNORECASE,
)


def _mask_labelled(match: re.Match[str]) -> str:
    value = match.group("value")
    if value.startswith(MASK):
        return match.group(0)
    return match.group("label") + MASK


def _mask_all(_match: re.Match[str]) -> str:
    return MASK


def _keep_alt(match: re.Match[str]) -> str:
    return match.group("alt")


# D-17: ![alt](url) -> alt. Bounded alt and url lengths keep the scan linear.
_IMAGE_RE = re.compile(
    r"!\[(?P<alt>[^\]\n]{0,500})\]\((?P<url>[^)\s]{1,2000})(?:\s+\"[^\"\n]{0,200}\")?\)"
)

# Query parameter names that carry credentials or signatures (case-insensitive).
_SIGNED_PARAMS: Final[frozenset[str]] = frozenset(
    {
        "token",
        "access_token",
        "sig",
        "signature",
        "x-amz-signature",
        "x-amz-credential",
        "x-goog-signature",
        "x-goog-credential",
        "key",
        "auth",
        "code",
        "expires",
        "x-goog-expires",
        "se",
        "sp",
        "sv",
    }
)
_URL_RE = re.compile(r"https?://[^\s<>()\[\]\"']{1,4000}")
_URL_TRAILING = ".,;:!?"


def _strip_signed_query(match: re.Match[str]) -> str:
    raw = match.group(0)
    url = raw.rstrip(_URL_TRAILING)
    trailing = raw[len(url) :]
    base, sep, rest = url.partition("?")
    if not sep:
        return raw
    query, hash_sep, fragment = rest.partition("#")
    names = {param.partition("=")[0].lower() for param in re.split(r"[&;]", query)}
    if names.isdisjoint(_SIGNED_PARAMS):
        return raw
    return base + hash_sep + fragment + trailing


_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN (?:[A-Z0-9 ]{1,40} )?PRIVATE KEY(?: BLOCK)?-----"
    r"[\s\S]{0,20000}?"
    r"-----END (?:[A-Z0-9 ]{1,40} )?PRIVATE KEY(?: BLOCK)?-----"
)

# Well-known credential prefixes (research A9). Values are at least 20 characters.
_TOKEN_PREFIX_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:"
    r"gh[pousr]_[A-Za-z0-9]{36}"
    r"|github_pat_[A-Za-z0-9_]{22,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|xox[abprs]-[A-Za-z0-9-]{10,}"
    r"|AIza[0-9A-Za-z_-]{35}"
    r"|sk-[A-Za-z0-9_-]{20,}"
    r"|pk_[A-Za-z0-9_]{20,}"
    r")"
)

_JWT_RE = re.compile(
    r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}"
)

# Candidate IBANs; only those passing the ISO 13616 mod-97 check are masked.
_IBAN_RE = re.compile(
    r"(?<![A-Za-z0-9])[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,3})?(?![A-Za-z0-9])"
)


def _iban_checksum_ok(candidate: str) -> bool:
    iban = candidate.replace(" ", "").upper()
    if not 15 <= len(iban) <= 34 or not iban.isalnum():
        return False
    rearranged = iban[4:] + iban[:4]
    digits = "".join(str(int(ch, 36)) for ch in rearranged)
    return int(digits) % 97 == 1


def _mask_iban(match: re.Match[str]) -> str:
    candidate = match.group(0)
    parts = candidate.split(" ")
    # A trailing uppercase word can be swallowed by the candidate: try shorter heads.
    for k in range(len(parts), 0, -1):
        if _iban_checksum_ok("".join(parts[:k])):
            tail = " ".join(parts[k:])
            return MASK + (" " + tail if tail else "")
    return candidate


# Italian mobile numbers: optional +39/0039, leading 3, 9-10 digits. Numbers starting with 0
# (office lines, D-16) and 11-digit P.IVA-like numbers never match.
_MOBILE_RE = re.compile(r"(?<![\w+/])(?:(?:\+|00)39[ .-]?)?3\d{2}[ .-]?\d{3}[ .-]?\d{3,4}(?!\w)")

_EMAIL_RE = re.compile(
    r"(?<![\w.+%-])[A-Za-z0-9._%+-]{1,64}@"
    r"(?P<domain>[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63}){1,8})"
)


def _mask_private_email(allowed: frozenset[str]) -> Callable[[re.Match[str]], str]:
    def replace(match: re.Match[str]) -> str:
        domain = match.group("domain").lower()
        if any(domain == a or domain.endswith("." + a) for a in allowed):
            return match.group(0)
        return MASK

    return replace


# URLs are matched first so a token-like path segment inside a URL is never touched.
_ENTROPY_RE = re.compile(
    r"(?P<url>https?://[^\s<>()\[\]\"']{1,4000})"
    r"|(?P<cand>(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+/=_-]{24,})"
)
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_HEX_RE = re.compile(r"[0-9a-fA-F]+")
_ENTROPY_THRESHOLD: Final = 4.2


def _shannon_entropy(value: str) -> float:
    total = len(value)
    return -sum(n / total * math.log2(n / total) for n in Counter(value).values())


def _mask_high_entropy(match: re.Match[str]) -> str:
    candidate = match.group("cand")
    if candidate is None:
        return match.group(0)
    if not (re.search(r"[A-Za-z]", candidate) and re.search(r"[0-9]", candidate)):
        return candidate
    if _HEX_RE.fullmatch(candidate) or _UUID_RE.fullmatch(candidate):
        return candidate
    if _shannon_entropy(candidate) < _ENTROPY_THRESHOLD:
        return candidate
    return MASK


def _build_rules(email_allow_domains: frozenset[str]) -> tuple[Rule, ...]:
    return (
        Rule("image_link", _IMAGE_RE, _keep_alt),
        Rule("signed_url_query", _URL_RE, _strip_signed_query),
        Rule("labelled_secret", _LABEL_RE, _mask_labelled),
        Rule("private_key_block", _PRIVATE_KEY_RE, _mask_all),
        Rule("token_prefix", _TOKEN_PREFIX_RE, _mask_all),
        Rule("jwt", _JWT_RE, _mask_all),
        Rule("iban", _IBAN_RE, _mask_iban),
        Rule("mobile_number", _MOBILE_RE, _mask_all),
        Rule("private_email", _EMAIL_RE, _mask_private_email(email_allow_domains)),
        Rule("high_entropy", _ENTROPY_RE, _mask_high_entropy),
    )


class Redactor:
    """Applies the registered rules in ``RULE_NAMES`` order and reports per-rule counts."""

    def __init__(self, *, email_allow_domains: frozenset[str]) -> None:
        rules = {rule.name: rule for rule in _build_rules(email_allow_domains)}
        self._rules: tuple[Rule, ...] = tuple(rules[name] for name in RULE_NAMES)

    @classmethod
    def from_settings(cls, s: SyncSettings) -> Redactor:
        return cls(email_allow_domains=s.redact_email_allow_domains)

    def redact(self, text: str) -> RedactionResult:
        hits: list[RuleHit] = []
        for rule in self._rules:
            count = 0

            def _sub(match: re.Match[str], _rule: Rule = rule) -> str:
                nonlocal count
                replacement = _rule.replace(match)
                if replacement != match.group(0):
                    count += 1
                return replacement

            text = rule.pattern.sub(_sub, text)
            if count:
                hits.append(RuleHit(rule.name, count))
        return RedactionResult(text=text, hits=tuple(hits))


def log_hits(logger: logging.Logger, source_id: str, hits: Sequence[RuleHit]) -> None:
    """Log one INFO record per hit: source id, rule name and count only."""
    for hit in hits:
        logger.info("redaction source=%s rule=%s count=%d", source_id, hit.rule, hit.count)
