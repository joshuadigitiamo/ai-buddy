# API Coverage — ClickUp Public API v3 (Docs)

> Full coverage by default. Opt-outs are explicit, reasoned decisions.
> Surface: the v3 Docs endpoints under `/api/v3/workspaces/{workspace_id}/docs` (ClickUp Public API v3 OpenAPI, read in 01-RESEARCH.md). Phase 1 integrates the read path of one doc (SYNC-01).

| capability | decision | reason |
|---|---|---|
| getDocPages (GET /docs/{doc_id}/pages, max_page_depth, content_format) | INTEGRATE | |
| getDocPageListing (GET /docs/{doc_id}/page_listing) | OPT-OUT | not needed: /pages returns the same tree plus content and dates in one call; the listing has no dates (research Pitfall 4) |
| getPage (GET /docs/{doc_id}/pages/{page_id}) | OPT-OUT | not needed: one /pages call per run already returns every page; per-page fetches would only add requests |
| getDoc (GET /docs/{doc_id}) | OPT-OUT | not needed: the doc id comes from CLICKUP_DOC_ID and no doc-level metadata is indexed |
| searchDocs (GET /docs) | OPT-OUT | not needed: the sync reads one configured doc and never discovers docs |
| createDoc (POST /docs) | OPT-OUT | explicitly out of scope: write actions on ClickUp are Out of Scope in REQUIREMENTS.md |
| createPage (POST /docs/{doc_id}/pages) | OPT-OUT | explicitly out of scope: write actions on ClickUp are Out of Scope in REQUIREMENTS.md |
| editPage (PUT /docs/{doc_id}/pages/{page_id}) | OPT-OUT | explicitly out of scope: write actions on ClickUp are Out of Scope in REQUIREMENTS.md |

Note: the Guides repository is read with the `git` CLI over HTTPS (clone/fetch), not through the GitHub REST API, so it has no API surface to enumerate here.
