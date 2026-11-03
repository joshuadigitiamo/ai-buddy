"""Single redaction filter every source passes through before anything is stored.

Rules are a fixed-order table (``RULE_NAMES``). Log records carry source id, rule name and
count only, never the matched value (D-14).
"""

from __future__ import annotations

import logging
import re
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


def _build_rules(email_allow_domains: frozenset[str]) -> tuple[Rule, ...]:
    del email_allow_domains  # used by the private_email rule once registered
    return (Rule("labelled_secret", _LABEL_RE, _mask_labelled),)


class Redactor:
    """Applies the registered rules in ``RULE_NAMES`` order and reports per-rule counts."""

    def __init__(self, *, email_allow_domains: frozenset[str]) -> None:
        self._email_allow_domains = email_allow_domains
        rules = {rule.name: rule for rule in _build_rules(email_allow_domains)}
        self._rules: tuple[Rule, ...] = tuple(rules[name] for name in RULE_NAMES if name in rules)

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
