---
milestone: v1
milestone_name: "Milestone 1 — personal dev use (Joshua)"
audited: 2026-11-07T00:00:00Z
status: gaps_found
scores:
  requirements: 29/41
  phases: 3/5
  integration: 11/11
  flows: 4/4
gaps:
  requirements:
    - { id: "INFRA-01", status: "unsatisfied", phase: "Phase 4", claimed_by_plans: [], completed_by_plans: [], verification_status: "missing", evidence: "Phase 4 not started; no phase directory" }
    - { id: "INFRA-02", status: "unsatisfied", phase: "Phase 4", claimed_by_plans: [], completed_by_plans: [], verification_status: "missing", evidence: "Phase 4 not started (docker-compose.dev.yml exists from 03-12 but no emulator round-trip compose)" }
    - { id: "INFRA-03", status: "unsatisfied", phase: "Phase 4", claimed_by_plans: [], completed_by_plans: [], verification_status: "missing", evidence: "Phase 4 not started" }
    - { id: "INFRA-04", status: "unsatisfied", phase: "Phase 4", claimed_by_plans: [], completed_by_plans: [], verification_status: "missing", evidence: "Phase 4 not started" }
    - { id: "INFRA-05", status: "unsatisfied", phase: "Phase 4", claimed_by_plans: [], completed_by_plans: [], verification_status: "missing", evidence: "Phase 4 not started" }
    - { id: "INFRA-06", status: "unsatisfied", phase: "Phase 4", claimed_by_plans: [], completed_by_plans: [], verification_status: "missing", evidence: "Phase 4 not started" }
    - { id: "EVAL-01", status: "unsatisfied", phase: "Phase 5", claimed_by_plans: [], completed_by_plans: [], verification_status: "missing", evidence: "Phase 5 not started" }
    - { id: "EVAL-02", status: "unsatisfied", phase: "Phase 5", claimed_by_plans: [], completed_by_plans: [], verification_status: "missing", evidence: "Phase 5 not started" }
    - { id: "EVAL-03", status: "unsatisfied", phase: "Phase 5", claimed_by_plans: [], completed_by_plans: [], verification_status: "missing", evidence: "Phase 5 not started" }
    - { id: "EVAL-04", status: "unsatisfied", phase: "Phase 5", claimed_by_plans: [], completed_by_plans: [], verification_status: "missing", evidence: "Phase 5 not started" }
    - { id: "EVAL-05", status: "unsatisfied", phase: "Phase 5", claimed_by_plans: [], completed_by_plans: [], verification_status: "missing", evidence: "Phase 5 not started" }
    - { id: "EVAL-06", status: "unsatisfied", phase: "Phase 5", claimed_by_plans: [], completed_by_plans: [], verification_status: "missing", evidence: "Phase 5 not started; milestone gate itself lives here" }
  integration:
    - { from: "jobs/sync (ArtifactStore)", to: "mcp_server snapshot", severity: "warning", reqs: ["SYNC-07", "MCP-01", "INFRA-04"], issue: "snapshot.py:77 hard-wires LocalDirArtifactStore; no store selector in McpSettings; cold-start-only load" }
    - { from: "chat_bot MCP_AUDIENCE", to: "mcp_server MCP_PUBLIC_BASE_URL / BOT_SA_EMAILS", severity: "warning", reqs: ["MCP-07", "BOT-04"], issue: "audience and bot SA identity must match across services; only documented, no startup check" }
    - { from: "chat_bot image", to: "buddy_mcp/models.py", severity: "warning", reqs: ["BOT-04", "INFRA-01", "INFRA-05"], issue: "bot imports buddy_mcp.models (mcp_client.py:21); CI path filters and build context must include it" }
    - { from: "mcp_server + chat_bot auth guards", to: "non-Cloud-Run hosts", severity: "warning", reqs: ["MCP-07"], issue: "K_SERVICE is the only deployed marker (mcp config.py:88, bot config.py:126); fails open on k8s/other hosts" }
    - { from: "chat_bot", to: "mcp_server over http", severity: "warning", reqs: ["BOT-04", "INFRA-02", "INFRA-03"], issue: "plain-http MCP_URL loopback-only (421 otherwise); dev compose relies on shared netns" }
  flows: []
tech_debt:
  - phase: 01-content-sync
    items:
      - "run-unit-tests.sh still mode 100644 in git index (fresh clone needs chmod +x)"
      - ".planning/PROJECT.md active list still describes content sync in ClickUp terms (stale after D-25)"
      - "buddy_sync run logs redaction hits with source=<file stem> on stderr; matters once logs are hosted (Phase 4)"
      - "No 01-SECURITY.md (secure-phase never run for Phase 1)"
      - "01-VALIDATION.md status: draft (Nyquist NOT-VALIDATED)"
  - phase: 02-mcp-server-and-skill
    items:
      - "02-REVIEW-DISPOSITION: 9 findings still 'open' (untriaged): WR-01 K_SERVICE-only guard, WR-02 loopback prefix accepts localhost.evil.com, WR-03 gap log stores raw sensitive question text, WR-04 tool descriptions contradict Skill, WR-05 OAUTH_JWT_SIGNING_KEY min length not enforced, IN-01..IN-04"
      - "Deferred to Phase 4: claude.ai connector live check; live rejection of non-digitiamo account"
      - "Deferred to Phase 5: Skill behaviour with a live model (EVAL-03)"
  - phase: 03-google-chat-bot
    items:
      - "WINDOWS #1 open: live bot-to-MCP Google ID token call unverified (Phase 4 deploy)"
      - "WINDOWS #5 open: parking-style out-of-index classification is model behaviour (Phase 5 golden set)"
      - "WINDOWS #7 open: Guarda button downloads mp4 (GitHub release assets, private repo, 238/2524 rows with offsets) — Phase 4 SC5"
      - "Real Chat-signed HTTP JWT path unverified live (Phase 4)"
      - "VIDEO_THUMBNAIL_URL placeholder; GUIDES_WEB_BASE required with no default — Phase 4 deploy config"
      - "Gate reason labels internal only (gate.py GateResult.reason); Phase 5 eval needs to read them"
nyquist:
  compliant_phases: ["02", "03"]
  partial_phases: []
  not_validated_phases: ["01"]
  missing_phases: []
  overall: partial
---

# Milestone 1 Audit — AI Buddy Digitiamo

**Verdict: gaps_found.** Milestone is mid-flight: phases 1–3 done and verified, phases 4 (Infra/CI-CD) and 5 (Evaluation + milestone gate) not started. The 12 unsatisfied requirements are exactly INFRA-01..06 and EVAL-01..06. No defect found in phases 1–3; cross-phase wiring is complete.

> Update 2026-11-14 (audit itself is as of 2026-11-07, not re-run): Phase 4 is in progress — 04-01 and 04-02 complete, 04-03 running; Phase 5 not started. 04-02 added an explicit fail-closed `DEPLOY_ENV`, `MCP_ALLOWED_HOSTS` and `/healthz` on the MCP server (integration warning 4 / WR-01 on the MCP side). The GCP project for deploys exists: `ai-buddy-dev` (ID in docs/internal/gcp-project.md, gitignored), digitiamo.com org, billing linked. The PROJECT.md "ClickUp terms" tech-debt item was fixed on 2026-11-14.

## Phases

| Phase | Verification | Plans | Nyquist | Security | Notes |
|-------|--------------|-------|---------|----------|-------|
| 01 Content Sync | passed (8/8) | 11/11 | NOT-VALIDATED (draft) | no SECURITY.md | 4 non-blocking warnings |
| 02 MCP Server and Skill | passed (5/5) | 7/7 | compliant | verified, 0 open | 9 review findings untriaged; 3 live checks deferred |
| 03 Google Chat Bot | passed (8/8) | 12/12 | compliant | verified, 0 open | 3 WINDOWS entries open; Guarda deferred |
| 04 Infrastructure and CI/CD | missing | 0 | — | — | not started |
| 05 Evaluation and Gate | missing | 0 | — | — | not started |

## Requirements (3-source cross-reference)

| REQ | Phase | VERIFICATION | SUMMARY frontmatter | REQUIREMENTS.md | Final |
|-----|-------|--------------|---------------------|-----------------|-------|
| FND-01, FND-02, GUIDE-01 | 1 | passed | 01-01 (+GUIDE-01 in 01-02..01-11) | [x] | satisfied |
| SYNC-01..SYNC-07 | 1 | passed | listed (01-02..01-11) | [x] | satisfied |
| MCP-01..MCP-08 | 2 | passed | listed (02-01, 02-02, 02-04..02-07) | [x] | satisfied |
| BOT-01..BOT-11 | 3 | passed | listed (03-01..03-12) | [x] | satisfied |
| INFRA-01..06 | 4 | missing | missing | [ ] | **unsatisfied** |
| EVAL-01..06 | 5 | missing | missing | [ ] | **unsatisfied** |

29/41 satisfied. No orphans among phase 1–3 requirements. 02-03-SUMMARY lists no `requirements-completed` (its MCP-05/MCP-07 work is credited by 02-07), harmless.

Notes carried by verifiers: MCP-07 satisfied with live items deferred to Phase 4; MCP-08 satisfied for content, live behaviour scheduled for EVAL-03; BOT-02 live JWT a Phase 4 item; BOT-09 card live, Guarda playback deferred.

## Integration (gsd-integration-checker, static trace; key claims spot-checked)

Connected 11, orphaned 3 (all intentional: `handbook_get`, `guides_get_section`, `handbook://{pagina}` serve Skill/claude.ai, not the bot), missing 0.

| Flow | Status |
|------|--------|
| sync → index → MCP tool → cited result | complete |
| Chat DM → bot → MCP → LLM → gate → card | complete (bot validates tool output with `buddy_mcp.models`) |
| unanswerable → refusal → Firestore gap | complete |
| Guides video → video_url → Guarda button | complete in code; hosting issue (WINDOWS #7) |

### Latent Phase 4 blockers (warnings)

1. `services/mcp_server/buddy_mcp/snapshot.py:77` hard-wires `LocalDirArtifactStore`; Phase 4 needs a GCS (or baked) adapter + selector variable. Load is cold-start only. (SYNC-07, MCP-01, INFRA-04)
2. Bot `MCP_AUDIENCE` must equal MCP `MCP_PUBLIC_BASE_URL`, and `BOT_SA_EMAILS` must hold the bot SA; no startup check. Add a deploy smoke test. (MCP-07, BOT-04)
3. `services/chat_bot/buddy_bot/mcp_client.py:21` imports `buddy_mcp.models`; CI path filters/build context must include it, or move models to `buddy_core`. (BOT-04, INFRA-01, INFRA-05)
4. `K_SERVICE`-only production marker in both configs; fails open on kind/other free hosts. Add explicit `DEPLOY_ENV`. Same as 02-REVIEW WR-01. (MCP-07)
5. Plain-http MCP URL loopback-only; separate deployments need https or shared netns. (BOT-04, INFRA-02, INFRA-03)

## Tech debt

See frontmatter `tech_debt` (14 items across 3 phases). Highest-value before Phase 4: triage 02-REVIEW WR-01/WR-02/WR-05 (deploy-time security), chmod +x `run-unit-tests.sh` (CI will hit it), and the five integration warnings above, which are naturally Phase 4 plan inputs.

## Nyquist

| Phase | VALIDATION.md | Compliant | Action |
|-------|---------------|-----------|--------|
| 01 | exists (draft) | not validated | `/gsd-validate-phase 1` |
| 02 | exists | true | — |
| 03 | exists | true | — |
