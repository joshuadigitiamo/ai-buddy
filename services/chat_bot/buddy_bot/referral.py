"""Referente lookup (D-04): the role comes from the shared table, the contact from the handbook.

A contact is accepted only when it is a verbatim substring of a handbook page the search
returned in this run. Nothing from the model or the repository is ever used as a contact.
"""

from typing import Final

from buddy_bot.mcp_client import McpToolError, evidence_from
from buddy_bot.ports import LlmClient, LlmError, McpTools
from buddy_bot.prompts import CONTACT_SYSTEM, format_evidence
from buddy_bot.schemas import ContactExtraction, Referente
from buddy_mcp.models import GuidesSearchOutput

CONTACT_QUERY_SUFFIX: Final = " contatti"
CONTACT_MAX_TOKENS: Final = 300

_NO_GUIDES: Final = GuidesSearchOutput(status="no_results", query="", results=[])


async def resolve_referente(role: str, *, tools: McpTools, llm: LlmClient, model: str) -> Referente:
    """Name the role, adding a contact only when the handbook writes it verbatim.

    Never raises for a model or tool failure: a refusal must not fail because of the lookup.
    """
    try:
        handbook = await tools.handbook_search(role + CONTACT_QUERY_SUFFIX)
        if handbook.status == "no_results":
            return Referente(role=role)
        pages = [e for e in evidence_from(handbook, _NO_GUIDES).values() if e.kind == "handbook"]
        extraction = await llm.structured(
            ContactExtraction,
            model=model,
            system=CONTACT_SYSTEM,
            user=f"Ruolo: {role}\n\n{format_evidence(pages)}",
            max_tokens=CONTACT_MAX_TOKENS,
        )
    except (LlmError, McpToolError):
        return Referente(role=role)
    contact = (extraction.contact or "").strip()
    source = next((p for p in pages if p.source_url == extraction.source_url), None)
    if not contact or source is None or contact not in source.text:
        return Referente(role=role)
    return Referente(role=role, contact=contact, contact_source=source)
