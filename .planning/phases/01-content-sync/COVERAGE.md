# API Coverage — Phase 1

> Full coverage by default. Opt-outs are explicit, reasoned decisions.
> Since D-25 (2026-11-03) Phase 1 integrates no external API: the handbook is read from a local folder and the Guides from a local git checkout. The former Docs-API integration (plans 01-04 to 01-07) was removed in plan 01-10. The table keeps the capabilities that integration covered, so the decision history stays visible.

| capability | decision | reason |
|---|---|---|
| getDocPages (GET /docs/{doc_id}/pages, max_page_depth, content_format) | OPT-OUT | removed by D-25: the tracker is being shut down; the handbook is read from a local folder |
| getDocPageListing (GET /docs/{doc_id}/page_listing) | OPT-OUT | removed by D-25: the tracker is being shut down; the handbook is read from a local folder |
| getPage (GET /docs/{doc_id}/pages/{page_id}) | OPT-OUT | removed by D-25: the tracker is being shut down; the handbook is read from a local folder |
| getDoc (GET /docs/{doc_id}) | OPT-OUT | removed by D-25: the tracker is being shut down; the handbook is read from a local folder |
| searchDocs (GET /docs) | OPT-OUT | removed by D-25: the tracker is being shut down; the handbook is read from a local folder |
| createDoc (POST /docs) | OPT-OUT | removed by D-25: the tracker is being shut down; the handbook is read from a local folder |
| createPage (POST /docs/{doc_id}/pages) | OPT-OUT | removed by D-25: the tracker is being shut down; the handbook is read from a local folder |
| editPage (PUT /docs/{doc_id}/pages/{page_id}) | OPT-OUT | removed by D-25: the tracker is being shut down; the handbook is read from a local folder |

Note: the Guides repository is read with the `git` CLI (clone), not through the GitHub REST API, so it has no API surface to enumerate here. The clone source is a local path (the read-only mount of the Guides checkout, D-27).
