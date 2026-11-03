# index.db format (schema 1.0.0)

The sync job publishes one SQLite file, `index.db`. This document is the contract for every reader of that file. The reference implementation is `packages/buddy_core` (`schema.py`, `index_writer.py`, `index_reader.py`).

## Purpose and consumers

| Consumer | Phase | Use |
|----------|-------|-----|
| `services/mcp_server` | 2 | Serves handbook pages and Guides search to Claude |
| Evaluation harness | 5 | Measures retrieval quality (Recall@5) against the Guides chunks |
| `jobs/sync` | 1 | Reads the previous artifact to decide what changed (incremental state) |

Consumers must read the file through `buddy_core.index_reader.open_index`. It is the only supported SQL surface; table layouts below can change inside a major version only by adding nullable columns.

## File

- One SQLite file. The writer sets `journal_mode=DELETE`, runs `VACUUM`, and closes the connection, so no `-wal`, `-shm` or `-journal` file exists beside it.
- `PRAGMA user_version` holds the schema major version (`1` for schema 1.0.0). It is a cheap check that does not need any table.
- Readers open the file read-only (`file:<path>?mode=ro`).
- The file is built under a temporary name in the same directory and moved into place with `os.replace`, so a reader sees either the old file or the new one, never a half-written file.

## Versioning

- `schema_version` is semver, stored in `meta`. A consumer refuses an artifact whose major differs from the major it was built for. `open_index` raises `IndexVersionError` when either `PRAGMA user_version` or the major part of `meta.schema_version` differs.
- A column added with a default, or a new nullable column, is a minor bump. Renaming, removing or re-typing a column, or changing the meaning of a key such as `chunk_key`, is a major bump and needs a re-sync.
- `build_id` = UTC timestamp `%Y%m%dT%H%M%SZ`, a hyphen, and the first 12 hex characters of `content_hash`. Example shape: `20261103T100000Z-0123456789ab`.
- `content_hash` is the sha256 of the canonical JSON (`sort_keys`, compact separators, `ensure_ascii=False`) of the logical rows: `schema_version`, `source_doc_id`, `guides_commit_sha`, `pipeline_version`, `redaction_version`, handbook rows sorted by `page_id`, chunk rows sorted by `chunk_key`, video rows sorted by `chunk_key`. It never covers SQLite file bytes, `build_id` or `created_at_utc`, because file bytes are not a stable function of content.
- Unchanged content gives an unchanged hash, so the sync job writes no new artifact. Two builds of the same content at different times therefore differ only in `build_id` and `created_at_utc`.
- Only the latest artifact is kept in the artifact directory. "Versioned" means `schema_version` + `build_id` + manifest, not a retained history of builds.

## Tables

### meta

| Column | Type | Null | Meaning |
|--------|------|------|---------|
| `key` | TEXT PK | no | One of the keys below |
| `value` | TEXT | no | Value as text |

Keys (all required; a missing key raises `IndexFormatError`):

| Key | Meaning |
|-----|---------|
| `schema_version` | Semver of this format |
| `build_id` | See Versioning |
| `content_hash` | See Versioning |
| `guides_commit_sha` | Commit of the Guides repo that was indexed |
| `source_doc_id` | Id of the source handbook document (value comes from the environment) |
| `pipeline_version` | Version of the sync pipeline that produced the rows |
| `redaction_version` | Version of the redaction rules applied before storing text |
| `created_at_utc` | ISO-8601 UTC time of the build |

### handbook_pages

One row per handbook page, in document order.

| Column | Type | Null | Meaning |
|--------|------|------|---------|
| `page_id` | TEXT PK | no | Source page id |
| `parent_id` | TEXT | yes | Parent page id, null for a top-level page |
| `position` | INTEGER UNIQUE | no | Order in the document tree walk; unique per artifact |
| `depth` | INTEGER | no | Nesting depth, 0 for top level |
| `title` | TEXT | no | Page title (redacted) |
| `url` | TEXT | no | Deep link to the page in the source tool |
| `date_edited_raw` | INTEGER | yes | Source edit timestamp, unmodified (epoch milliseconds) |
| `date_created_raw` | INTEGER | yes | Source creation timestamp, unmodified |
| `revision_date_iso` | TEXT | yes | `YYYY-MM-DD` derived from `date_edited_raw`, else from `date_created_raw` |
| `content_md` | TEXT | no | Full page markdown (redacted) |
| `content_hash` | TEXT | no | sha256 of the stored (redacted) content only |

`content_hash` columns never hash pre-redaction text: a masked low-entropy secret could otherwise be recovered by guessing against the hash.

### guide_chunks

One row per Guides chunk. `id` is assigned 1..n in `(file, line_start, part_index)` order.

| Column | Type | Null | Meaning |
|--------|------|------|---------|
| `id` | INTEGER PK | no | Row id, also the FTS5 rowid and the final search tie-break |
| `chunk_key` | TEXT UNIQUE | no | Stable key, see below |
| `file` | TEXT | no | Path inside the Guides repo |
| `h2` | TEXT | no | Parent `##` heading text |
| `h3` | TEXT | yes | `###` heading text, null for a `##` chunk |
| `heading` | TEXT | no | Display heading: `h3` when present, else `h2` |
| `line_start` | INTEGER | no | First line, 1-based, inclusive |
| `line_end` | INTEGER | no | Last line, 1-based, inclusive |
| `part_index` | INTEGER | no | Part number when an oversized section is split into several chunks |
| `text` | TEXT | no | Chunk text (redacted) |

`chunk_key` format (`make_chunk_key`): `<file>#<slug(h2)>/<slug(h3) or _>/<part_index>`, with `~N` appended when the same key occurs N > 1 times in one file. It is heading-based so that it survives line shifts. `slug` is NFKD-normalised, lowercase ASCII, with each run of other characters replaced by one hyphen.

### guide_chunks_fts

External-content FTS5 table over `guide_chunks` (`content='guide_chunks'`, `content_rowid='id'`), indexed columns `h2`, `heading`, `text`, tokenizer `porter unicode61 remove_diacritics 2`. It is filled with the FTS5 `'rebuild'` command after the bulk insert.

### video_map

Rows exist only for chunks whose guide has a video.

| Column | Type | Null | Meaning |
|--------|------|------|---------|
| `chunk_key` | TEXT PK, FK to `guide_chunks.chunk_key` | no | Chunk the video belongs to |
| `video_url` | TEXT | no | Base URL of the full video, without a fragment |
| `part` | INTEGER | no | Video part number, 1 for single-part videos |
| `start_seconds` | REAL | yes | Scene start inside that part; null for a README fallback |
| `source` | TEXT | no | `scene` (scene start known) or `readme_fallback` (guide has a video, no scene mapping) |

## Search

- `IndexReader.search_guides(query, limit=5)` is BM25 keyword search over `guide_chunks_fts`. Column weights are `h2` 4.0, `heading` 6.0, `text` 1.0 (`bm25(guide_chunks_fts, 4.0, 6.0, 1.0)`).
- Quoting rule (`to_match_query`): the query is split on whitespace, NUL bytes count as whitespace, tokens without any alphanumeric character are dropped, each remaining token is wrapped in double quotes with embedded quotes doubled, and tokens are joined with `OR`. FTS5 operators and column filters in user text are therefore inert. The expression is passed as a bound parameter (`MATCH ?`).
- A query with no searchable token returns an empty list. `search_guides` does not raise on any user string. `limit` is clamped to 1..50.
- Results are ordered by score, then by chunk `id`, so equal scores come back in a stable order.
- The index is English-only. The Italian-to-English bridge is the caller's job: the Skill or bot sends English keywords (decision D-21). Retrieval stays BM25-only until the Phase 5 evaluation shows a Guides Recall@5 below 0.8.

## Video links

The base URL and the offset are stored separately (decision D-01). `buddy_core.models.video_link` composes the playable link: `<video_url>#t=<whole seconds>` when `start_seconds` is set, the bare `video_url` otherwise. A media-fragment `#t=` helps only when the player opens the file inline; storing the parts separately lets a later change of host replace only the base URL.

## Incremental state

Incremental state lives in the previous artifact (D-10). The sync job opens the last `index.db` and compares each page's `date_edited_raw` and `content_hash`. There is no separate state file. The manifest below is for consumers that want to check freshness without opening the database.

## Loading

Consumers load the artifact at cold start only (D-11). There is no hot reload: a new artifact takes effect when the consumer process starts again.

## Manifest

`index.manifest.json` sits beside `index.db` and is written with the same temporary-file-plus-`os.replace` method, after `index.db` itself.

| Field | Meaning |
|-------|---------|
| `schema_version` | Same as `meta.schema_version` |
| `build_id` | Same as `meta.build_id` |
| `content_hash` | Same as `meta.content_hash` |
| `created_at_utc` | Same as `meta.created_at_utc` |
| `sha256` | sha256 of the `index.db` bytes |
| `size_bytes` | Size of `index.db` in bytes |

The `sha256` here is a transfer check on file bytes. It is not the logical `content_hash`.

## Not indexed

- Pages on the sync denylist: dropped before processing and never written, hashed or counted.
- `date_updated`: the source tool's update timestamp must never influence indexing, so no column holds it.
- Text above a guide's first `##` heading (title and table of contents).
- Image attachment URLs: the alt text is kept, the URL is removed.
- Any pre-redaction text, or any hash of it.

## Handoff

How the artifact reaches the MCP container is recorded in [ADR 0001](adr/0001-index-handoff.md): an `ArtifactStore` port with a local-directory adapter now, bucket versus baked image decided with the hosting platform in Phase 4.

## Changelog

- 1.0.0: first published format.
