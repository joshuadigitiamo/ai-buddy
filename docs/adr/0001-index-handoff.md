# ADR 0001: How the index artifact reaches the MCP server

## Status

Accepted (Phase 1, decision D-12); decision completed in Phase 4 (04-CONTEXT D-06 to D-10).

## Context

- The sync job writes `index.db` (see [index-format.md](../index-format.md)). `mcp_server` must read it. Requirement SYNC-07 asks how the artifact reaches the MCP container.
- The user wants hosting to be free if possible. That reopens the hosting choice (D7: Cloud Run needs an active billing account even at about zero cost), so the platform is not settled in Phase 1. (Update 2026-11-14: the existing GCP project `ai-buddy-dev` already has a billing account linked, so the billing account is no longer an open prerequisite. The decision below is unchanged.)
- The repository is public. No public image may contain handbook content, so an image that bakes the artifact in must stay private.

## Options

| Option | Pro | Con |
|--------|-----|-----|
| Rebuild the image with the artifact baked in | No runtime storage dependency; fastest cold start | Every sync needs an image build and deploy; the image holds handbook text and must be private |
| Read from an object-storage bucket at cold start | Image stays generic and can be public; sync and deploy are decoupled | Needs a bucket, credentials and a hosting platform that offers a free tier for it |
| Local directory (`ARTIFACT_DIR`) | Works today, on a laptop and in `docker compose`, with no cloud account | Not a production handoff by itself |

## Decision

Phase 1 is host-agnostic (D-12). `buddy_core` defines an `ArtifactStore` interface (`latest_path`, `staging_path`, `publish`, `discard`) and ships one adapter, `LocalDirArtifactStore`, which reads and writes the directory named by `ARTIFACT_DIR`. Publishing stages a file in the same directory and moves it with `os.replace`, so readers never see a partial file.

Bucket versus baked image is not chosen now. It is chosen together with the hosting platform in Phase 4.

## Phase 4 decision

Phase 4 chooses the bucket read (D-06). The choice is final for the hosted deployment; the Consequences section states what switching away from it costs.

- **Reader.** `GcsArtifactStore` (in `buddy_core`) is the second adapter behind `ArtifactStore`. It reads a private bucket in `europe-west8` through a small `BucketPort`; only `GcsBucket` imports the storage client. `mcp_server` picks it with `ARTIFACT_STORE=gcs`, `ARTIFACT_BUCKET` and `ARTIFACT_PREFIX`, and loads the index at cold start (D-11 stays: no hot reload).
- **Object layout and publish order.** The db is stored as `<prefix>index-<build_id>.db` and a pointer as `<prefix>index.manifest.json` (the six manifest fields plus `object`). Publishing uploads the db object, checks the md5 the bucket reports, and overwrites the pointer last. A reader follows the pointer only, so an interrupted publish leaves readers on the previous build. The server refuses to start on a bad pointer, a sha256 or size mismatch, or any object name other than `index-<build_id>.db`.
- **Writer.** The sync runs on demand on the developer's laptop, in the `sync` image, and `scripts/sync-and-publish.sh` runs it and then `python -m buddy_sync publish` (D-06, D-07). Nothing runs on a schedule: there is no Cloud Scheduler and no Cloud Run job (D-07, D-09).
- **Forced revision.** After a new publish the script updates the `mcp-server` Cloud Run service (`--update-env-vars INDEX_BUILD_ID=<build_id>`), which creates a new revision; the next request cold-starts on the new index and the revision carries the served build id (D-08). A publish that finds the same content hash in the pointer uploads nothing and forces no revision.
- **Other environments.** `docker compose` and `kind` keep `LocalDirArtifactStore` over a mounted directory (D-10). The server image is the same in every environment; only configuration differs.
- **The image stays generic.** It contains no handbook content, so it could be public. The handbook content lives only in the private bucket and on the laptop.

## Consequences

- Phase 2 (`mcp_server`) reads the artifact only through `ArtifactStore` and `open_index`, and loads it at cold start (D-11).
- Phase 4 added `GcsArtifactStore` without changing any caller of `ArtifactStore`.
- Any image that bakes the artifact in must stay private.
- Switching to a baked image later is costly (D-06). It needs a private image registry entry, a CI image rebuild and deploy for every sync, and a change to INFRA-01's rule that one generic image serves every environment. The bucket, the pointer layout and the publish script would be retired.
- Old builds stay in the bucket: nothing deletes them by age, because an age-based delete would remove the build the pointer still names after a month without a sync and the server would then refuse to start. Rolling back means rewriting the pointer to an older build that is still there.
- `REQUIREMENTS.md` SYNC-07 and INFRA-04 are reworded to match this decision.
- The store supports a single writer. Two concurrent sync runs against one `ARTIFACT_DIR` are outside the supported model; the last successful publish wins atomically.
