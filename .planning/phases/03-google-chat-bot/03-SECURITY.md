---
phase: "03"
slug: "google-chat-bot"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-11-07"
---

# Phase 03 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Register built from the `<threat_model>` blocks of 03-01..03-12 PLAN.md. Verification depth: ASVS L1 (grep-level evidence in implementation and tests). Block threshold: high.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| PyPI / GitHub -> images and dev compose | new direct packages and the Meridian source commit | third-party code |
| repository data file -> bot process | escalation YAML read at startup | public, roles only |
| internet -> HTTP endpoint | any caller can POST; only Google-signed Chat requests may pass | Chat events (identity, question text) |
| Pub/Sub topic -> bot | anyone with publish rights can inject events | Chat events |
| Chat event -> BotService.handle | sender identity and text are untrusted | identity, question text |
| other Chat apps -> bot | bot senders could create reply loops | events |
| MCP tool output -> answer prompt | handbook/Guides text may carry instructions | internal handbook text |
| user question -> reformulation prompt | direct prompt-injection carrier | question text |
| LLM output -> gate, referente, user message | untrusted until validated against run evidence | answer prose, citations, contacts |
| bot -> gap log | question text crosses into stored data | question text, tried queries (no identity) |
| environment / secret store -> BotSettings | secrets and mode switches enter at startup | API keys, HMAC secret |
| bot -> LLM backend (Meridian or Anthropic API) | prompts leave the process | question + evidence |
| bot -> Firestore (EU) | conversation text at rest | pseudonymous turns, 24 h |
| bot -> MCP server | service-to-service call with an ID token | ID token, queries |
| bot -> Google Chat API | app credentials post messages | replies |
| host credentials -> Meridian container | Claude Max login in a named volume | OAuth credentials |
| service-account key file -> bot container | Google credentials, read-only mount | SA key |
| process logs -> log sink | logs leave the process | fixed texts, exception type names |
| repository (public) -> README, compose, `.env.example`, Dockerfile | setup docs are public | no secrets |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-03-01 | Tampering | answer citations (forged ids) | high | mitigate | `gate.py:29` rejects any citation not in run evidence; links rendered from Evidence; `test_tracer.py:92` forged-citation test | closed |
| T-03-02 | Elevation of privilege | BotService.handle for non-allowlisted sender | high | mitigate | `service.py:112` allowlist check before any Chat/MCP/LLM call; tracer zero-call test | closed |
| T-03-03 | Information disclosure | logs in service and workflow | medium | mitigate | all `_LOGGER` calls in `service.py`/`workflow.py` use fixed text + `type(exc).__name__`; `test_log_hygiene.py` | closed |
| T-03-04 | Tampering | escalation YAML loading | low | mitigate | `buddy_core/escalation.py:83` `yaml.safe_load`; drift test `test_escalation.py:54` | closed |
| T-03-05 | Information disclosure | contacts in public YAML | medium | mitigate | `escalation_topics.yaml` holds roles only (0 e-mail matches at audit) | closed |
| T-03-06 | Elevation of privilege | allowlist matching (case, prefix, missing sender) | high | mitigate | `service.py:64,85` exact set membership after strip/lower; `service.py:110` None/bot dropped; `test_allowlist.py` prefix/case cases | closed |
| T-03-07 | Denial of service | redelivered events, bot loops | medium | mitigate | `service.py:33-34` dedupe 600 s / 1024; bot senders dropped; run deadline `service.py:61` | closed |
| T-03-08 | Information disclosure | logs of dropped/failed events | medium | mitigate | `service.py:113` fixed drop line; `test_allowlist.py:151` asserts no `users/`, `@`, name | closed |
| T-03-09 | Tampering | malformed / hostile event JSON | low | mitigate | `events.py` `normalize_event` returns None on any malformed field; parametrized cases | closed |
| T-03-10 | Tampering | indirect prompt injection in retrieved text | high | mitigate | `prompts.py:172-188` `<fonte>` delimiting with closing-tag guard and attribute escaping; citations gated; links/referral rendered by bot | closed |
| T-03-11 | Tampering | prompt injection in user question | medium | mitigate | refusal/referral strings fixed in code (`render.py:158,197`); answer gated to evidence; `test_sensitive.py` safe branch | closed |
| T-03-12 | Spoofing | fabricated referente contact | high | mitigate | `referral.py:41-42` contact must be verbatim substring of a page returned this run; `test_refusal.py:86,104` | closed |
| T-03-13 | Information disclosure | gap record content | medium | mitigate | `mcp_client.py:144` sends only question + tried queries; `test_workflow.py:120,139` read the gap log | closed |
| T-03-14 | Information disclosure | secrets in validation errors | high | mitigate | `config.py:44` `hide_input_in_errors`, `SecretStr` fields; sentinel tests (`test_llm_client.py:266,300`) | closed |
| T-03-15 | Elevation of privilege | Meridian used by more than one person | high | mitigate | `config.py:112` refuses meridian with >1 ALLOWED_USERS; README visibility "Joshua only" (`README.md:113`) | closed |
| T-03-16 | Information disclosure | LangSmith/LangChain tracing export | high | mitigate | `config.py:19,149-151` refuses true tracing vars; `Dockerfile:42` sets false; dev compose sets false | closed |
| T-03-17 | Denial of service | LLM backend hang | medium | mitigate | `llm.py:125,134` client timeout; `LlmUnavailableError` (`llm.py:112`); service run deadline | closed |
| T-03-18 | Spoofing | unauthenticated MCP calls on Cloud Run | high | mitigate | `config.py:126` MCP_AUTH=none refused with K_SERVICE; `config.py:133` MCP_AUDIENCE required for ID-token auth | closed |
| T-03-19 | Information disclosure | conversation data at rest (D-10) | high | mitigate | `memory.py` HMAC key, shape `turns/updated_at/expire_at` only, 24 h TTL (`:28,60`), text caps (`:56`), N-turn cap (`:86`) | closed |
| T-03-20 | Information disclosure | guessable thread keys | medium | mitigate | HMAC-SHA256 (`memory.py:41`); secret ≥ 32 chars (`config.py:20,82`) | closed |
| T-03-21 | Tampering | lost turns under concurrent writes | low | accept | see Accepted Risks AR-03-01 | closed |
| T-03-22 | Tampering | model-written links / Chat markup in answer | high | mitigate | `render.py:49-54` `sanitize_prose` strips URLs and angle brackets; links only from Evidence | closed |
| T-03-23 | Spoofing | button to non-web scheme | medium | mitigate | `render.py:42,85,128-129` http(s) only | closed |
| T-03-24 | Information disclosure | thumbnail fetch reveals usage | low | accept | see Accepted Risks AR-03-02 | closed |
| T-03-25 | Spoofing | forged Chat event on HTTP endpoint | high | mitigate | `intake/http.py:135-152` `verify_oauth2_token` with exact audience, issuer e-mail match, token shape/size guard; 401 without detail | closed |
| T-03-26 | Spoofing | forged event on Pub/Sub topic | medium | mitigate | README IAM step (`README.md:122-124`): publisher role only to Chat's identity; allowlist still applies | closed |
| T-03-27 | Denial of service | oversized bodies, poison Pub/Sub messages | medium | mitigate | `intake/http.py:35,200` 1 MiB cap → 413; `intake/pubsub.py:51` ack-always; `:111` FlowControl max_messages | closed |
| T-03-28 | Information disclosure | access logs, tokens in errors | medium | mitigate | `intake/http.py:240` `access_log=False`; token verified and discarded; `test_http_intake.py:333` | closed |
| T-03-29 | Information disclosure | secrets in `.env.example`, Dockerfile, startup errors | high | mitigate | `test_repo_layout.py:68-74,172` rejects secret-suffixed keys incl. `_API_KEY`; errors name variables only | closed |
| T-03-30 | Elevation of privilege | container running as root | medium | mitigate | `Dockerfile:51` `USER 10001` in chat_bot stage | closed |
| T-03-31 | Information disclosure | logs pairing identity with question text | high | mitigate | `test_log_hygiene.py` sentinel test over paths/loggers; access log off | closed |
| T-03-32 | Spoofing | bot calling MCP without identity on Cloud Run | high | mitigate | `mcp_client.py:30-44` `GoogleIdTokenAuth` with audience; K_SERVICE guard (T-03-18); server-side check (Phase 2 D-12) | closed |
| T-03-33 | Information disclosure | ID token leakage | medium | mitigate | token in memory only; `test_id_token_auth.py:161-162` asserts absence from error chain and caplog; no fetch at startup (`test_main.py:144`) | closed |
| T-03-34 | Information disclosure | Meridian credentials | high | mitigate | `docker-compose.dev.yml` named volume `meridian-claude` only; no host `~/.claude` bind, nothing in image or repo | closed |
| T-03-35 | Elevation of privilege | Meridian reachable beyond compose network | high | mitigate | no `ports` on any service (`test_dev_compose.py:46`); `MERIDIAN_API_KEY` required (`:?` guard); D1a guard (T-03-15) | closed |
| T-03-36 | Tampering | Meridian image supply chain | high | mitigate | build context pinned to SHA `cafdcf78…` (`docker-compose.dev.yml:20`); `test_dev_compose.py:52` | closed |
| T-03-37 | Information disclosure | bot service-account key | high | mitigate | `${BOT_SA_KEY_FILE}` from shell env, mounted `:ro` (`docker-compose.dev.yml:92`); absent from `.env.example` | closed |
| T-03-38 | Spoofing | forged events on Pub/Sub topic | medium | mitigate | README IAM step restricts publisher; see Notes on add-on SA deviation | closed |
| T-03-39 | Repudiation | phase decision record | low | mitigate | `03-CONTEXT.md:132` `## Amendments (03-01 checkpoint)` block; overrides tagged in 03-01-SUMMARY | closed |
| T-03-SC | Tampering | pip installs, Meridian commit, emulator image | high | mitigate | 03-01 legitimacy gate approved by Joshua (03-01-SUMMARY:109,123); `==` pins in `services/chat_bot/requirements.txt`; shared firestore pin equal to MCP server; emulator `google/cloud-sdk:592.0.0-emulators` reused | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

### Notes

- **T-03-26 / T-03-38 deviation:** the plan named `chat-api-push@system.gserviceaccount.com` as sole publisher. Live check showed add-on-format apps publish as `service-<project-number>@gcp-sa-gsuiteaddons.iam.gserviceaccount.com`; README documents both formats and restricts publish to the one in use. Intent (single publisher) preserved.
- **Dev compose uses `MCP_AUTH: none`** over localhost (shared network namespace). Permitted outside Cloud Run; the K_SERVICE guard (T-03-18) refuses it when deployed. Phase 4 must keep ID-token auth on the deployed path.
- **T-03-SC rows** from 03-02..03-09 (accept, "no new package") consolidated into the single mitigated T-03-SC row above.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-03-01 | T-03-21 | Single user; last-write-wins can only drop history turns, never add identity | Joshua (03-07 plan) | 2026-11-07 |
| AR-03-02 | T-03-24 | One static thumbnail chosen by Joshua; fetched by Google Chat's proxy, not the bot | Joshua (03-01 decision) | 2026-11-07 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-07 | 40 | 40 | 0 | /gsd-secure-phase (orchestrator, L1 grep verification; auditor short-circuited per workflow rule) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-11-07
