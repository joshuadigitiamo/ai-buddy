# Phase 1: Content Sync - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-03
**Phase:** 01-content-sync
**Areas discussed:** Video mapping, Index artifact + handoff, Redaction policy, Guides scope + chunking

---

## Video mapping

| Question | Options | Selected |
|----------|---------|----------|
| Link target | Full video + timestamp / Cut per-scene clips / Full video only | Full video + timestamp |
| Scene match | Explicit map file / Heuristic match / Chapter-level only | Explicit map file |
| Map home | Guides repo / AI Buddy repo | Guides repo |
| Timestamps | Computed from durations.json / Typed in map file | Computed from durations.json |
| No map entry | Full video, no timestamp / No video | Full video, no timestamp |
| Multi-part | Map gives part + offset / You decide | Map gives part + offset |
| Phase 1 map scope | Format + loader + 1-2 videos / All videos / Format + loader only | Format + loader + 1-2 videos |

**Notes:** Scout found no published scene clips (release has full videos only) and no scene → section map.

---

## Index artifact + handoff

| Question | Options | Selected |
|----------|---------|----------|
| Format | Single SQLite file / Bundle directory | Single SQLite file |
| Handoff | GCS bucket at startup / Baked into image | (reopened, see below) |
| Versioning | schema_version + content hash / Timestamp only | schema_version + content hash |
| Sync state | Inside previous artifact / Separate state file | Inside previous artifact |
| Refresh | Cold start only / Periodic check | Cold start only |
| Storage in Phase 1 | Local + GCS adapter on emulator / Local only / Bake into image / **Host-agnostic, defer to Phase 4** | Host-agnostic, defer to Phase 4 |

**Notes:** User asked what GCS is and whether it is free, and stated the goal "host the project somewhere maybe free". Explained: GCS is Google Cloud Storage; free tier is US-only; europe-west8 cost for a few MB is < 1 cent/month, but a billing account is required (as for Cloud Run). Open-source S3 alternatives (MinIO, SeaweedFS, Garage) need an always-on server. Outcome: Phase 1 stays host-agnostic; D7 hosting and the handoff are revisited in Phase 4.

---

## Redaction policy

| Question | Options | Selected |
|----------|---------|----------|
| Exclude by | Page-id denylist / Title match / Both | Page-id denylist |
| On detect | Mask span + warn / Drop page / Fail sync | Mask span + warn |
| Rules (multi) | Password/PIN labels, Token/key patterns, Personal data, Signed URLs | All four |
| People data | Keep work contacts, mask private / Mask all personal contacts | Keep work contacts, mask private |
| Images | Drop links, keep alt text / Keep with tokens stripped | Drop links, keep alt text |
| Guides scan | Same filter / Handbook only | Same filter |

**Notes:** Scan of the raw snapshot: Wi-Fi page is the only credential; company billing ids are legitimate content.

---

## Guides scope + chunking

| Question | Options | Selected |
|----------|---------|----------|
| Files | *_GUIDE.md + design doc / *_GUIDE.md only / every .md | *_GUIDE.md + design doc |
| Chunk size | H3 with H2 parent / H2 / You decide | H3 with H2 parent |
| IT vs EN | Caller translates query / Bilingual keywords at sync / Defer to eval | Caller translates query |
| Source | git clone by URL + token / Local mount / Both by env | git clone by URL + token |
| Section map | Sync derives it / Create GUIDES_INDEX.md in Guides | Create GUIDES_INDEX.md in Guides |
| Guides sync | Skip if SHA unchanged / Always full rebuild | Skip if SHA unchanged |

**Notes:** Scout found `GUIDES_INDEX.md` (assumed by D5) does not exist.

---

## Claude's Discretion

- GUIDES_INDEX.md generator location and drift handling
- sections.yaml schema, durations.json parsing
- ClickUp REST v3 client, recorded fixtures
- Sync CLI, SQLite schema detail, entropy threshold, foundation details

## Deferred Ideas

- Revisit D7 hosting (free options) and artifact handoff in Phase 4
- Fill remaining video maps
- Per-scene clip assets
- Italian synonyms per chunk if Recall@5 < 0.8
