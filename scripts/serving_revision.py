#!/usr/bin/env python3
"""Name the Cloud Run revision that holds 100% of a service's traffic (INFRA-05, 04-22).

Usage:
    gcloud run services describe <service> --format=json \\
        | python3 scripts/serving_revision.py <service>

The describe JSON goes in on stdin; the revision name comes out on stdout. The answer is read from
`status.traffic`, the resolved list. `spec.traffic` is the requested list: after `update-traffic
--to-latest` it holds only `{latestRevision: true, percent: 100}` with no revision name, so it
cannot name anything. A document without a usable `status.traffic` is an error, never an empty
answer: an empty answer is how CI recognises a first deploy.

Exit 0 and one line on stdout when exactly one target holds 100% and its name belongs to the
service. Exit 2 with a names-only `::error::` line on stderr for anything else (split traffic,
unresolved list, a revision of another service, invalid JSON). The input is never echoed. Standard
library only, so the runner and the test image need nothing installed.
"""

import json
import re
import sys
from typing import Any

_SERVICE = re.compile(r"[a-z][a-z0-9-]{0,40}")
_FAILURE_EXIT = 2


def _fail(message: str) -> int:
    print(f"::error::{message}", file=sys.stderr)
    return _FAILURE_EXIT


def _percent(target: Any) -> int | None:
    """Percent of one traffic target; a missing value is 0 (the API omits it at 0%)."""
    if not isinstance(target, dict):
        return None
    percent = target.get("percent", 0)
    if isinstance(percent, bool) or not isinstance(percent, int):
        return None
    return percent


def serving_revision(document: Any, service: str) -> str | None:
    """The revision holding 100% in `status.traffic`, or None when the list is not clear-cut."""
    status = document.get("status") if isinstance(document, dict) else None
    traffic = status.get("traffic") if isinstance(status, dict) else None
    if not isinstance(traffic, list) or not traffic:
        return None
    percents = [_percent(target) for target in traffic]
    if any(percent is None for percent in percents):
        return None
    holders = [t for t, percent in zip(traffic, percents, strict=True) if percent and percent > 0]
    if len(holders) != 1 or _percent(holders[0]) != 100:
        return None
    name = holders[0].get("revisionName")
    pattern = rf"{re.escape(service)}-[a-z0-9]([a-z0-9-]{{0,50}}[a-z0-9])?"
    if not isinstance(name, str) or not re.fullmatch(pattern, name):
        return None
    return name


def main(argv: list[str]) -> int:
    if len(argv) != 1 or not _SERVICE.fullmatch(argv[0]):
        return _fail("usage: serving_revision.py <service>")
    service = argv[0]
    unresolved = f"traffic of {service} is split or unresolved; resolve it by hand before deploying"
    try:
        document = json.load(sys.stdin)
    except ValueError:
        return _fail(unresolved)
    name = serving_revision(document, service)
    if name is None:
        return _fail(unresolved)
    print(name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
