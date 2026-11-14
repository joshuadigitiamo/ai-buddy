# ADR 0001: How the index artifact reaches the MCP server

## Status

Accepted (Phase 1, decision D-12).

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

## Consequences

- Phase 2 (`mcp_server`) reads the artifact only through `ArtifactStore` and `open_index`, and loads it at cold start (D-11).
- Phase 4 adds one `ArtifactStore` adapter (or bakes the file into a private image) without changing any caller.
- Any image that bakes the artifact in must stay private.
- `REQUIREMENTS.md` SYNC-07 and INFRA-04 are reworded to match this decision.
- The store supports a single writer. Two concurrent sync runs against one `ARTIFACT_DIR` are outside the supported model; the last successful publish wins atomically.
