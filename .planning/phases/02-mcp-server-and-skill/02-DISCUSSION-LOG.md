# Phase 2: MCP Server and Skill - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-06
**Phase:** 02-mcp-server-and-skill
**Areas discussed:** Handbook search + citations, Tool output contract, Auth + bot-to-server, Skill + escalation contacts

---

## Handbook search + citations

| Question | Options | Selected |
|----------|---------|----------|
| handbook_search mechanism | In-memory FTS5 / FTS5 table in index.db / Titles only | In-memory FTS5 |
| Hit unit | Whole page / Heading section / Page + snippet | Whole page |
| Guides source URL | GitHub permalink (SHA) / Branch link / Internal URI | GitHub permalink |
| Handbook source URL | handbook://id only / Optional base URL env | handbook://id only |
| Italian tokenization | unicode61 + prefix / Italian stemmer / You decide | Italian stemmer |

## Tool output contract

| Question | Options | Selected |
|----------|---------|----------|
| Result format | Structured + text / Markdown only | Structured + text |
| handbook_get() no section | TOC / Full handbook | TOC |
| No results | Empty list + status / MCP error | Empty list + status |
| Gap retention | 90d / 30d / You decide | 90 days |
| Top-k | 5 fixed / 5 default + limit max 10 | 5 default + limit max 10 |
| Gap fields | Minimal / Plus tools tried + build_id | Plus tools tried + build_id |

## Auth + bot-to-server

| Question | Options | Selected |
|----------|---------|----------|
| Library | You decide after research / mcp SDK / fastmcp | You decide after research |
| Bot auth | SA ID token / API key / Network only | SA ID token |
| Rate limit | In-memory per identity / Shared DB counter | In-memory per identity |
| Auth off guard | Env + refuse on Cloud Run / Env only | Env + refuse on Cloud Run |
| Gap store | Port + Firestore / Port + Postgres / Direct Firestore | Port + Firestore |

**Notes:** User asked "what is Firestore?" and "can't we use PgVector?". Explained Firestore (serverless GCP doc DB, gap log only, emulator in tests) and that pgvector is for embeddings (not needed per D5); Postgres could hold the gap log. User kept Firestore behind a port.

## Skill + escalation contacts

| Question | Options | Selected |
|----------|---------|----------|
| Contacts | Roles in Skill + names from handbook / Gitignored file / Role mailboxes | Roles + handbook |
| Escalation list | Claude drafts, Joshua reviews / Joshua writes | Claude drafts, Joshua reviews |
| Skill language | English instr + Italian answers / All Italian | English + Italian answers |
| Install guide | claude.ai / Desktop / Claude Code | All three |

## Claude's Discretion

- Server/OAuth library (researcher), output field names, config/env names, resource listing, rate-limit defaults, stemmer details.

## Deferred Ideas

- Gap log backend Firestore vs Postgres (Phase 4).
- Vector search only if Recall@5 < 0.8 (Phase 5).
