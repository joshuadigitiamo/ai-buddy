# Synthesis Summary (entry point for gsd-roadmapper)

Mode: new. Precedence: ADR > SPEC > PRD > DOC; docs/PLAN.md is SPEC with precedence 0 (highest); docs/research/*.md are DOC. Within PLAN.md, section 2.1 (03/11/2026) overrides section 2.

## Doc counts by type
- Total: 8 (SPEC 1, DOC 7, ADR 0, PRD 0, UNKNOWN 0)
- SPEC: docs/PLAN.md
- DOC: docs/research/01-handbook-inventory.md, 02-meridian-e-backend-ai.md, 03-onboarding-best-practices.md, 04-handbook-gap-analysis.md, 05-modelli-open-self-hosted.md, 06-hosting-modello-self-hosted.md, 07-costi-hosting-cloud-run.md
- docs/PLAN.md re-read from disk after classification; includes D16 and test doc id xkwgt-39975 (D14).

## Decisions
- 18 entries in decisions.md (D1, D1a, D2-D16). Treated as locked per orchestrator instruction (no ADR status in source). Tentative parts flagged: D7 region "da confermare"; D9 alternative open-model proposal.
- Supersessions: D1a over D1 (personal dev only); D7a refines D7; D13 over D3 and Phase 2 gating.
- File: /home/digitiamo/Desktop/WORK/AI BUDDY/.planning/intel/decisions.md

## Requirements
- 16 entries (no PRDs in set; derived from explicit PLAN.md statements): REQ-grounded-cited-answers, REQ-no-source-refusal-and-gap-log, REQ-sensitive-topic-escalation, REQ-mcp-server-five-tools, REQ-mcp-auth-google-domain, REQ-sync-clickup-guides, REQ-sync-redaction, REQ-skill-digitiamo-buddy, REQ-google-chat-bot, REQ-pluggable-llm-client, REQ-chat-video-cards, REQ-dockerized-everything, REQ-infra-ci-cd, REQ-golden-set-eval, REQ-apply-guides-best-practices, REQ-handbook-content-cleanup (outside M1 code).
- File: /home/digitiamo/Desktop/WORK/AI BUDDY/.planning/intel/requirements.md

## Milestone 1 phase mapping (user intent, from orchestrator)
1. ClickUp + Guides sync with redaction: REQ-sync-clickup-guides, REQ-sync-redaction (D14, D5)
2. MCP server, 5 tools: REQ-mcp-server-five-tools, REQ-mcp-auth-google-domain, REQ-no-source-refusal-and-gap-log (D10)
3. Google Chat bot (Pub/Sub dev, pluggable LLM client meridian|api, allowlist, video cards): REQ-google-chat-bot, REQ-pluggable-llm-client, REQ-chat-video-cards, REQ-skill-digitiamo-buddy (D13, D1a, D15)
4. Infra (Docker, kind, Cloud Run, GitHub Actions): REQ-dockerized-everything, REQ-infra-ci-cd (D7a, D11, D12)
5. Golden-set eval: REQ-golden-set-eval (see WARNING on golden set authorship)
Cross-cutting: REQ-apply-guides-best-practices (D16), REQ-grounded-cited-answers, REQ-sensitive-topic-escalation.

## Constraints
- 18 entries: api-contract 3, schema 2, protocol 3, nfr 10. Includes Python-only / Docker / pip / ruff / pytest / mypy / run-unit-tests.sh conventions (marked as orchestrator/user global config where not in PLAN.md).
- File: /home/digitiamo/Desktop/WORK/AI BUDDY/.planning/intel/constraints.md

## Context topics
- 9 topics in context.md (handbook inventory and quality, sensitive content, ClickUp API notes, Meridian/Anthropic terms, onboarding best practices, gap analysis and RAG writing rules, open-weight models, LLM hosting, Cloud Run costs; Phase 2 alternative material is outside Milestone 1). No credentials copied.
- File: /home/digitiamo/Desktop/WORK/AI BUDDY/.planning/intel/context.md

## Conflicts
- 0 blockers, 3 warnings (cycle-rule deviation, Max account sharing vs D1a, golden set authorship), 10 info (auto-resolved / notes). No competing PRD variants (no PRDs). No LOCKED-vs-LOCKED contradictions.
- Detail: /home/digitiamo/Desktop/WORK/AI BUDDY/.planning/INGEST-CONFLICTS.md

## Open items to carry into phase planning (unresolved in source)
- How sync data reaches the MCP container (image rebuild vs bucket read at startup), PLAN section 3.
- Region europe-west8 confirmation (D7).
- Real team chat and rollout channel; Team license budget; CCNL; official handbook owner; which Guides become company-wide; formal data-sovereignty constraint (PLAN section 10).
- Video hosting for non-dev users must move to Google Drive before rollout (D15).
- Cost of chat_bot service, Pub/Sub, CI/CD and kind not covered by research 07.

## Per-type intel files
- /home/digitiamo/Desktop/WORK/AI BUDDY/.planning/intel/decisions.md
- /home/digitiamo/Desktop/WORK/AI BUDDY/.planning/intel/requirements.md
- /home/digitiamo/Desktop/WORK/AI BUDDY/.planning/intel/constraints.md
- /home/digitiamo/Desktop/WORK/AI BUDDY/.planning/intel/context.md
