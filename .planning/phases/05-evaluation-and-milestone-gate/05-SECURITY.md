---
phase: "05"
slug: "evaluation-and-milestone-gate"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
block_on: high
created: "2026-11-22"
---

# Phase 05 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Register taken from the `<threat_model>` blocks of 05-01..05-17 PLAN.md (authored at plan time).
> Verified by gsd-security-auditor at ASVS L1 (static inspection of code, tests, compose, Dockerfile and git history; suite not re-run).

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| this repo -> Guides repo (private) | executor regenerates one index file in the private working tree | generated index (private) |
| laptop -> GCP bucket / Cloud Run | full publish changes the deployed index (owner action only) | index artifacts |
| PyPI / GHCR -> images | mlflow-skinny, pandas, numpy and the MLflow server image enter the build | third-party code |
| golden YAML -> loader | file content treated as untrusted input | eval items |
| eval -> MLflow server (loopback) | traces and feedback carry questions and handbook text | private text |
| eval -> PRIVATE_DIR cache / reports | cached replies, verdicts and JSON reports | private text |
| sources and bot answer -> judge prompt | untrusted text that could carry instructions | retrieved text, model output |
| eval -> MCP servers (real and empty fixture) | shared rate limiter; transport failures cross back | queries, results |
| eval -> Meridian (owner's Max session) | live calls on personal credentials | prompts, quota |
| private golden / live reports -> public repo | handbook-derived text and ids must not cross | none permitted |
| bot -> MCP server (05-14) | guides_search now carries the filtered standalone question | question text |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-05-01 | Tampering | Guides repository | medium | mitigate | only GUIDES_INDEX.md changed; commit by owner | closed |
| T-05-02 | Information disclosure | 05-01-SUMMARY.md | high | mitigate | SUMMARY holds SHAs, hashes, build ids, publish mode only | closed |
| T-05-03 | Elevation of privilege | owner gcloud login | medium | mitigate | executor ran no publish; owner ran it | closed |
| T-05-04 | Tampering | mlflow-skinny / pandas pins | high | mitigate | `==` pins, hashed lock, `--require-hashes` (Dockerfile:114), human approval | closed |
| T-05-05 | Information disclosure | chat_bot / mcp_server images | high | mitigate | `test_bot_and_server_locks_carry_no_mlflow`; LANGSMITH_TRACING=false | closed |
| T-05-06 | Information disclosure | MLflow client telemetry | medium | mitigate | MLFLOW_DISABLE_TELEMETRY in eval stage (Dockerfile:102), tested | closed |
| T-05-07 | Elevation of privilege | eval image | low | mitigate | USER 10001, no git, private-source guard | closed |
| T-05-08 | Information disclosure | golden.py public routing | high | mitigate | load error for public item citing the handbook scheme (golden.py:168-172), tested | closed |
| T-05-09 | Information disclosure | tracking URI | high | mitigate | http + host allow-list (config.py:59-70), tested | closed |
| T-05-10 | Information disclosure | cli/runner output | medium | mitigate | `test_question_text_never_reaches_stdout_stderr_or_logs` | closed |
| T-05-11 | Tampering | golden YAML parsing | medium | mitigate | `yaml.safe_load` + pydantic `extra="forbid"` | closed |
| T-05-12 | Information disclosure | mlflow port | high | mitigate | `127.0.0.1:5000` only, tested | closed |
| T-05-13 | Spoofing | MLflow Host header | medium | mitigate | explicit `--allowed-hosts`, no bare `*`, tested | closed |
| T-05-14 | Information disclosure | MLflow telemetry | medium | mitigate | disabled on server and eval service, tested | closed |
| T-05-15 | Elevation of privilege | root MLflow container | medium | mitigate | digest pin, cap_drop ALL, no-new-privileges, named volume | closed |
| T-05-16 | Information disclosure | eval service secrets | high | mitigate | only MERIDIAN_API_KEY by interpolation, tested | closed |
| T-05-17 | Information disclosure | cache directory | high | mitigate | PRIVATE_DIR/eval/cache; docs/internal gitignored and untracked | closed |
| T-05-18 | Tampering | stale cache entries | medium | mitigate | full outcome key incl. bot_version; trace-existence check, tested | closed |
| T-05-19 | Denial of service | corrupt cache file | low | mitigate | bad JSON = miss + WARNING; atomic replace, tested | closed |
| T-05-20 | Tampering | judge prompt injection | high | mitigate | fenced data blocks, closing tags neutralized, pydantic output, no tools, tested | closed |
| T-05-21 | Information disclosure | report console and logs | high | mitigate | text only in PRIVATE_DIR JSON; sentinel test | closed |
| T-05-22 | Repudiation | verdict provenance | low | mitigate | key carries judge model, prompt and scoring versions; report records models | closed |
| T-05-23 | Elevation of privilege | judge self-preference | medium | mitigate | JUDGE_MODEL != ANSWER_MODEL (config.py:79-80), tested | closed |
| T-05-24 | Information disclosure | jobs/eval/golden/ (public) | high | mitigate | privacy test + fail-first checker; loader refusal | closed |
| T-05-25 | Information disclosure | recall report | medium | mitigate | JSON under PRIVATE_DIR; console ids and rates only | closed |
| T-05-26 | Denial of service | MCP rate limiter | low | mitigate | one session, item pause, failures errored not missed | closed |
| T-05-27 | Tampering | fixture vs real artifacts | medium | mitigate | empty server mounts fixture volume read-only; single writer, tested | closed |
| T-05-28 | Repudiation | gap logging claim | medium | mitigate | gap_reported + emulator document-count cross-check | closed |
| T-05-29 | Information disclosure | empty-context report | low | mitigate | console ids/statuses/counts; JSON under PRIVATE_DIR | closed |
| T-05-30 | Information disclosure | guides.yaml | high | mitigate | privacy test, loader refusal; `git ls-files docs/internal` empty | closed |
| T-05-31 | Information disclosure | 05-11 SUMMARY / commits | high | mitigate | scan: no private golden text in tracked files or commit messages | closed |
| T-05-32 | Repudiation | review status | medium | mitigate | gate fails on draft (gate.py:44-46); approvals by owner | closed |
| T-05-33 | Tampering | gate verdict integrity | high | mitigate | pure evaluate; FAIL on unmeasured/errored/draft; smoke checks exit code | closed |
| T-05-34 | Denial of service | Max quota | medium | mitigate | readiness short-circuit with no model call; caches; error stop | closed |
| T-05-35 | Information disclosure | preflight output | medium | mitigate | ids, hosts, exception type names only, tested | closed |
| T-05-36 | Information disclosure | 05-13-SUMMARY.md | high | mitigate | verdict lines, numbers, ids, hashes only | closed |
| T-05-37 | Spoofing | Meridian credentials | medium | mitigate | key by compose interpolation only; `.env` ignored | closed |
| T-05-38 | Tampering | verdict after the fact | medium | mitigate | only gd-02 / gd-05 edited, per 05-GAP-DECISION; thresholds and judge untouched | closed |
| T-05-39 | Information disclosure | autolog during score | medium | mitigate | autolog suspended in try/finally (tracing.py), tested incl. raising path | closed |
| T-05-40 | Tampering | build_llm_client seam | low | mitigate | annotation-only change; bot lock mlflow-free | closed |
| T-05-41 | Denial of service | quota exhaustion | medium | mitigate | stop after max consecutive errors with resume hint, tested | closed |
| T-05-42 | Tampering | false PASS | high | mitigate | integer 90% test, boundary truth table; errored never wrong | closed |
| T-05-43 | Information disclosure | guides_search question text | medium | mitigate | no new log line; MCP and bot log-hygiene tests | closed |
| T-05-44 | Tampering | larger evidence set | medium | mitigate | `</fonte` escaping kept; injection-guard prompt test | closed |
| T-05-45 | Denial of service | extra MCP request | low | accept | see Accepted Risks AR-05-01 | closed |
| T-05-46 | Information disclosure | private golden edit | high | mitigate | gitignored file only; docs/internal untracked; no private text in commits | closed |
| T-05-47 | Information disclosure | lint issue text | medium | mitigate | handbook entries named by position only, tested | closed |
| T-05-48 | Tampering | golden edits after live results | medium | mitigate | id-level diff vs 6ad3dce: only the decided items changed | closed |
| T-05-49 | Denial of service | recall on MCP outage | low | mitigate | session failure errors remaining items, INCOMPLETE, tested | closed |
| T-05-50 | Tampering | verdict cache key | high | mitigate | `reply_digest` in verdict key (runner.py:194-197), tested | closed |
| T-05-51 | Repudiation | MLflow feedback vs report | medium | mitigate | verdict-digest marker + stale same-name feedback deletion; see note on WR-04 | closed |
| T-05-52 | Denial of service | collect on MCP outage | medium | mitigate | transport errors become errored items; error stop; report still written | closed |
| T-05-53 | Information disclosure | new error log lines | medium | mitigate | exception type name only; caplog sentinel tests | closed |
| T-05-54 | Information disclosure | 05-17-SUMMARY, disposition file | high | mitigate | verdict lines, ids, hashes, counts only | closed |
| T-05-55 | Spoofing | Meridian credentials | medium | mitigate | own long-lived token via compose interpolation (8ee67fb); host ~/.claude not mounted, tested | closed |
| T-05-56 | Tampering | verdict after the fact | medium | mitigate | recorded as printed; no code/golden commits after the gate run | closed |
| T-05-57 | Tampering | stale cached results | medium | mitigate | 05-13 cache moved aside; bot_version and reply_digest re-key entries | closed |
| T-05-SC | Tampering | npm/pip/cargo installs | high | mitigate (05-02) / accept (other plans) | 05-02 pins + hashes + human approval; see AR-05-02 | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

### Notes

- T-05-55: the plan's wording (credentials-file reseed) is outdated by 8ee67fb, which moved Meridian to its own long-lived token passed by compose interpolation. The intent (no credential printed or committed) holds.
- T-05-51: the declared mitigation is present. Code-review finding WR-04 (stale-feedback cleanup can also delete a human-entered MLflow label of the same name, and runs before `evaluate`) is a human-annotation integrity issue tracked as open in 05-REVIEW-DISPOSITION.md, not a register gap.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-05-01 | T-05-45 | One extra MCP request per first attempt; server limit 5 rps burst 30, eval item pause 0.5 s, retry adds no question search | plan 05-14 (owner-approved plan) | 2026-11-22 |
| AR-05-02 | T-05-SC | Plans other than 05-02 install no package; all lock, requirement and Dockerfile changes in Phase 5 belong to 05-02, which carries the mitigation | plans 05-01, 05-03..05-17 | 2026-11-22 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-22 | 58 | 58 | 0 | gsd-security-auditor (ASVS L1) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-11-22
