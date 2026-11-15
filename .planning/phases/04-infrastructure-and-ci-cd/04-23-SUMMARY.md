---
phase: 04-infrastructure-and-ci-cd
plan: 23
status: in-progress
---

# Phase 04 Plan 23: Cache, SBOM, provenance and scan Summary (draft, Task 2 record)

## Pin verification

- trivy-action tag `v0.36.0` -> annotated tag object `a9c7b0f06e461e9d4b4d1711f154ee024b8d7ab8` -> commit `ed142fd0673e97e23eac54620cfb913e5ce36c25` (the pinned SHA; tag created 2026-04-22).
- GHSA-69fq-xp46-6x23 affected: trivy binary 0.69.4, trivy-action < 0.35.0, setup-trivy < 0.2.6; DockerHub trivy images v0.69.5 and v0.69.6 are named compromised.
- trivy-action v0.36.0 pins setup-trivy `3fb12ec12f41e471780db15c232d5dd185dcb514` (v0.2.6).
- Chosen Trivy binary: `v0.76.2` (released 2026-11-05), set in the scan step `with.version`. A test rejects 0.69.4, 0.69.5 and 0.69.6.

## Local scan counts

Scanner: `aquasec/trivy@sha256:8f6bb947dbc528902e11f2f5be52f7b519f6a39d5d148f41166f2040499768fb` (0.76.2). Images built with `--target mcp_server` and `--target chat_bot` (Debian 13.7 on the pinned `python:3.12-slim`); Python dependencies: 0 findings. Counts are per package hit.

| Image | CRITICAL fixed | CRITICAL unfixed | HIGH fixed | HIGH unfixed |
|-------|----------------|------------------|------------|--------------|
| mcp-server | 0 | 0 | 2 | 47 |
| chat-bot | 0 | 0 | 2 | 47 |

Fixed (2 CVEs, zlib1g, fix `1:1.3.dfsg+really1.3.1-1+deb13u1`, not in the pinned base digest): CVE-2026-76844, CVE-2026-85091.

Unfixed (11 CVEs, all HIGH, Debian OS packages):
- util-linux family (36 of the 47 hits): CVE-2026-76642, CVE-2026-78408, CVE-2026-78409, CVE-2026-78410
- ncurses: CVE-2025-69720
- libsqlite3-0: CVE-2026-119373, CVE-2026-119374, CVE-2026-119379
- libsystemd0, libudev1: CVE-2026-16742
- libacl1: CVE-2026-54369
- perl-base: CVE-2026-9538

## Scan policy

Decision by Joshua (via the orchestrator, 2026-11-15): fail only on findings that have a fixed version (`ignore-unfixed: true`, as CICD_GUIDE section 16). Dependabot (04-21) moves the base image as fixes land; unfixed findings ship without a per-CVE record. The choice is reversible (one input).

scan-policy: fixable
