# Phase 5: Evaluation and Milestone Gate - Research

**Researched:** 2026-11-21
**Domain:** RAG evaluation harness (golden set, Recall@5, LLM-as-judge scoring, empty-context test, gate) plus self-hosted MLflow tracing, all in Docker, over an existing LangGraph bot and fastmcp server
**Confidence:** HIGH on MLflow/LangGraph behaviour (executed experiments against the real graph, pinned versions), MEDIUM on Meridian/Max behaviour (not probeable here)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

The owner chose the first four Golden-set answers explicitly, then said "On this phase accept all your recommendations": every remaining decision below is Claude's recommended option, approved by the owner.

#### Prerequisite (before drafting the golden set)
- **D-01:** The Guides checkout was fast-forwarded on 2026-11-21 to `4526500` (8 commits; 10 guides edited: RAG_CHATBOT, MCP_SERVERS, MULTI_AGENT_ARCHITECTURE_DESIGN, AIRFLOW, BIGQUERY_DATA_WAREHOUSE, BIG_DATA_FRAMEWORKS, ETL_VS_ELT, CICD, CLOUD_DEPLOYMENT, KUBERNETES; ETL vs ELT video re-cut). `GUIDES_INDEX.md` in the Guides repo was last updated 2026-11-03 and is stale. The first plan regenerates `GUIDES_INDEX.md` (the owner commits it in the Guides repo), re-runs the sync and publish (`sync-and-publish.sh`), and confirms the drift check is green, before any golden item is drafted. Golden expected sources are taken from that fresh index. Recall and scoring runs record the Guides commit and the index content hash.

#### Golden set
- **D-02:** Split storage. Guides items are committed (`eval/golden/guides.yaml`, or a path the planner picks). Handbook items live gitignored at `docs/internal/golden-handbook.yaml` (`docs/internal/` is already ignored; `docs/research/` is committed apart from `handbook-raw/`, so not there). The loader merges both files and warns loudly if the handbook file is missing; the gate then FAILs (incomplete set). Committed no-answer and sensitive items must not quote handbook text. — **Reversibility:** costly — committing handbook-derived content to the public repo cannot be undone (git history), so the split must hold from the first commit.
- **D-03:** About 40 items: 15 handbook-answerable, 13 Guides-answerable, 7 no-answer, 5 sensitive-escalation. Sensitive items cover both D-06 branches from Phase 3: a written general rule exists (cited rule + referral) and no rule exists (referral only).
- **D-04:** Item schema (fields; planner finalizes names): `id`, `kind` (`handbook | guides | no_answer | sensitive`), `question` (Italian), `expected_answer` (short reference answer), `key_facts` (list of facts a correct answer must contain), `expected_sources` (list of `source_url`: `handbook://<page_id>` or Guides permalink/section id), `expected_referente_role` (sensitive/no-answer), `review` (`draft | approved | rejected`), `review_note`. No item points at the official handbook doc.
- **D-05:** Review status gates the gate: scoring counts only `approved` items; the gate refuses PASS (prints FAIL "golden set not fully reviewed") while any item is `draft`. `rejected` items are excluded.
- **D-06:** Single-turn items only (empty history). Follow-up behaviour stays covered by Phase 3 tests.
- **D-07:** Claude drafts all items, the owner reviews them (an existing locked decision, see INGEST-CONFLICTS). Drafting is a plan task that ends in a human-review checkpoint.

#### Judging
- **D-08:** The LLM judge is Opus 5.5 (`claude-opus-5-5`), a different model from the Sonnet 5.5 answer step, to limit self-preference. It goes through the existing `LlmClient.structured()` and `LLM_BACKEND` (Meridian in M1), and the model id comes from config. MLflow's built-in provider judges are not used: they would need their own provider credentials or base_url wiring around Meridian.
- **D-09:** Correct-with-citation:
  - **Answerable items:** the reply is an answer, it contains every `key_facts` entry with nothing contradicting them (judge verdict), and at least one cited `source_url` is in `expected_sources` (deterministic check).
  - **No-answer items:** correct iff the reply is a refusal and a gap was logged.
  - **Sensitive items:** correct iff the reply is a referral naming the expected role, plus, in the rule-exists branch, a cited general rule from `expected_sources`.
  - The headline % is over all approved items.
- **D-10:** Invented policy. The judge receives the answer plus the full text of every source the answer cites, as the tools returned it in that run. It flags any normative claim (rule, obligation, entitlement, number, deadline, contact) that the cited text does not support. The invented-policy count is the number of answered items with at least one flagged claim. It is counted on every item that produced an answer, refusal items included if they wrongly answered.
- **D-11:** No human override of judge verdicts in M1. The report lists every failed item and every invented-policy flag, with the judge's reasoning and the MLflow trace link, for the owner to inspect. The judge prompt has deterministic unit tests (stub LLM) only.

#### Eval runtime and budget
- **D-12:** New eval package under `jobs/eval` (e.g. `buddy_eval`), with its own Dockerfile stage and its own requirements (mlflow pinned and passed through the legitimacy gate, like every new pin). Commands (names are planner's discretion): `recall`, `run`, `empty-context`, `gate`. Everything runs in Docker through a compose `eval` profile.
- **D-13:** Scoring runs `run_workflow` in-process in the eval container against the compose `mcp-server` over real MCP HTTP, with the real local index, the Firestore emulator gap log and the real LLM through `LLM_BACKEND` (the `meridian` compose service). No Chat API, no Cloud Run target.
- **D-14:** Budget control for Max limits (~40 items x ~3-4 bot calls + 1 judge call):
  - Sequential, with low fixed concurrency (1-2).
  - Per-item result cache keyed by golden-item hash + index hash + bot code/prompt version + model ids, so an interrupted or rate-limited run resumes and reruns are free.
  - An `--item` filter for single items.
- **D-15:** Recall@5 runs per answerable item: handbook items go to `handbook_search`, Guides items to `guides_search`. A hit is any `expected_sources` entry in the top 5. The query is the bot's actual Haiku reformulation, since raw Italian against English Guides BM25 would understate recall. The reformulation is cached (same cache as D-14), so after the first run Recall@5 costs no LLM calls. Guides Recall@5 < 0.8 prints the D5 hybrid-upgrade trigger. No-answer and sensitive items are excluded from Recall.
- **D-16:** Empty-context test:
  - Index: a second compose `mcp-server` instance points at a separate artifact volume holding a small committed fixture index of unrelated content. It is not an empty index, so cold-start guards don't fire.
  - Run: every approved answerable golden question goes through the real LLM.
  - Pass rule: PASS iff every reply is a refusal or referral and a gap is logged for each; any answer -> FAIL.
  - A deterministic stub-LLM variant also runs in the unit suite.
- **D-17:** The gate runs recall (informational, not gating), scoring and empty-context, reusing the per-item cache. It prints PASS only when correctness-with-citation >= 90%, invented = 0, empty-context passes and no item is `draft`. Otherwise it prints FAIL naming each failing metric. Non-zero exit on FAIL.

#### MLflow
- **D-18:** Trace eval runs only. The live/deployed bot is not traced in M1: privacy (traces hold handbook text and questions) and Cloud Run cost. The bot image gets no mlflow dependency.
- **D-19:** Instrumentation is MLflow autolog in the eval process (LangGraph/LangChain + Anthropic autolog). It yields one span per graph node (reformulate, retrieve, answer, gate, refuse/finish) plus LLM-call spans, with no bot code change. If research shows autolog misses node granularity on langgraph 1.2.x, the fallback is a no-op `Tracer` port in `buddy_bot` that eval injects.
- **D-20:** Scoring uses `mlflow.genai.evaluate` with a `predict_fn` wrapping `run_workflow` and custom scorers (`correctness`, `citation`, `invented_policy`) that call the D-08 judge. Verdicts attach to each trace, so every judged answer is inspectable in the UI with its retrieval, generation and gate spans. Run-level metrics are logged to the MLflow run. The researcher verifies async `predict_fn` support. If it is unsupported, the fallback is the D-14 runner plus `mlflow.log_feedback`.
- **D-21:** MLflow server is a compose service in the `eval` profile: pinned image, SQLite backend plus artifact store on a named local volume, UI bound to `127.0.0.1:5000`. Never deployed and never pushed anywhere. The volume holds handbook text, so it stays local, like the snapshot.

### Claude's Discretion
- Exact file paths and names (golden file location for Guides items, package and command names, cache location).
- Judge prompt wording and structured-output schema.
- Report format (console table + JSON artifact).
- Fixture content for the empty-context index.
- How `eval` profile services share networking with compose `mcp-server` and `meridian`.

### Deferred Ideas (OUT OF SCOPE)
- Human override of judge verdicts (a reviewed-verdict file the gate honours): revisit if judge disagreements show up.
- Tracing the live/deployed bot (production monitoring, MLFLOW_GENAI_GUIDE §19/§21): before any shared rollout.
- Running the LLM eval in CI: needs an API-key `LLM_BACKEND`, not Meridian.
- Hybrid dense+BM25 retrieval: its own phase, triggered only if Guides Recall@5 < 0.8 (D5).
- Multi-turn golden items exercising thread memory.
- HR-sourced golden set replacing the Claude-drafted one (when the official handbook is ready).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EVAL-01 | Golden set 30-50 Q&A, expected answer + source, answerable/no-answer/sensitive, the owner review status, none at the official handbook | Golden schema + split loader + lint (index-existence check, no `handbook://` in committed file); source-id matching section; D-01 prerequisite commands |
| EVAL-02 | One command: Recall@5 for handbook and Guides search, Guides < 0.8 flagged | Recall definition (guide §21), reformulation reuse by calling the `reformulate` node directly, pacing against the MCP rate limiter |
| EVAL-03 | One command scores golden set end to end via the bot workflow and `LLM_BACKEND`: correctness+citation, invented policies | `BotReply` carries everything needed (kind, sources with full text, referente, gap_reported); deterministic rule table; judge schema; trace-first run + `mlflow.genai.evaluate(data=traces)` |
| EVAL-04 | Empty-context test: every answer a refusal, gap logged, fails if any answer | Second mcp-server on fixture volume built by `build_index`; `reply.gap_reported` signal verified; fixture-overlap pitfall |
| EVAL-05 | Self-hosted containerized MLflow tracing of eval runs and workflow steps (retrieval, generation, gate) | Executed experiment: 1 trace per item, 12 spans (node spans + LLM spans); official image digest, flags, host-header fix, skinny client |
| EVAL-06 | Gate command PASS/FAIL against 90% / 0 invented / empty-context | Pure gate function + exit codes + failing-metric naming; cache reuse |
</phase_requirements>

## Summary

Every Phase 5 capability is buildable on the current codebase with **no change to the bot's behaviour and no mlflow dependency in the bot image**. I executed the real LangGraph workflow (`run_workflow`, langgraph 1.2.20, anthropic 2.6.0, the repo's own `stub_llm.py`) under `mlflow-skinny==3.18.0` against the official MLflow server image and confirmed: LangGraph autolog yields one span per graph node plus router spans; `mlflow.genai.evaluate` accepts an `async def predict_fn`; custom `@scorer` functions receive `inputs/outputs/expectations/trace`; feedback and expectations attach to the trace. Three behaviours of `mlflow.genai.evaluate` that the locked decisions did not anticipate must shape the plan (see "D-14 x D-20 interaction" below): it makes one extra real `predict_fn` call for "trace validation", it defaults to 10 worker threads, and a cached `predict_fn` result produces a hollow trace.

The one decision that needs the planner's (and ideally the owner's) explicit confirmation is how D-14 (per-item result cache so reruns are free) and D-20 (`predict_fn` wrapping `run_workflow`) fit together. Strictly following D-20 makes a cached rerun emit traces with no spans, which breaks EVAL-05 on every rerun. The verified alternative keeps D-20's intent (verdicts attach to each trace, `mlflow.genai.evaluate` still scores, run-level metrics are logged) by splitting into a **collect phase** (run the bot under tracing, cache outcome + `trace_id`) and a **score phase** (`mlflow.genai.evaluate(data=<list of Trace>)`, scorers read the cache for judge verdicts). This was executed end to end. Everything else in CONTEXT.md is confirmed feasible as written.

Two environment facts affect the plan: (1) the official `ghcr.io/mlflow/mlflow` image runs as root with no `USER` and fails to open SQLite on a fresh non-root named volume, and MLflow 3.x rejects the compose service-name Host header with 403 unless `--allowed-hosts` lists it (while `/health` stays 200, so a healthcheck will not catch it); (2) both new pins (`mlflow-skinny`, `pandas`) are rated `SUS` by the legitimacy seam purely because their latest release is under 30 days old and registry metadata lacked a repo URL; both are long-established projects, but the protocol still requires a `checkpoint:human-verify` before install.

**Primary recommendation:** Build `jobs/eval/buddy_eval` as a thin orchestration layer over the existing ports (`LlmClient`, `McpConnector`, `run_workflow`), with a collect-then-evaluate-over-traces MLflow design, `mlflow-skinny==3.18.0` + `pandas==3.1.1` pins (eval client), the official MLflow image pinned by digest as the server, and a pure, table-tested gate function; keep all MLflow calls behind one small module so unit tests stay hermetic.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Golden set storage, loading, lint | Eval job (files + loader) | Git (public/private split) | Data is files; public repo forces the split (D-02) |
| Retrieval (BM25/FTS) for Recall@5 | MCP server (existing `mcp-server` tools over HTTP) | Eval job (client) | Recall must measure the tools the bot really calls |
| Reformulation (Haiku) for recall queries | Bot workflow code (`reformulate` node, reused) | Eval cache | Same prompt/model as the bot (D-15) |
| End-to-end answer generation + gate | Bot workflow (`run_workflow`, unchanged) | Meridian (LLM) | Eval must not re-implement the bot |
| Gap logging signal | MCP server tool + Firestore emulator | Bot (`BotReply.gap_reported`) | Reply flag is set only after the tool returned `recorded` |
| Judging (facts, invented claims) | Eval job via `LlmClient` (Opus) | Meridian | D-08 |
| Deterministic scoring rules, gate | Eval job (pure functions) | - | Must be unit-testable without LLM or MLflow |
| Trace capture + feedback UI | MLflow server container (SQLite + artifacts) | Eval job (client, autolog) | D-18..D-21 |
| Empty-context index | Second `mcp-server` instance + fixture volume | Eval one-shot builds fixture | D-16 |
| Result/judge/reformulation cache and reports | Eval job, private bind mount `docs/internal/` | - | Contains handbook text; must never reach git |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `mlflow-skinny` | 3.18.0 (PyPI 2026-11-03) | Eval client: autolog tracing, `mlflow.genai.evaluate`, `@scorer`, `log_expectation`, REST client to the server | Executed against the pinned stack: tracing + `genai.evaluate` work; venv 454 MB vs 1004 MB for full `mlflow`; no sqlalchemy/flask/scipy/sklearn/matplotlib [VERIFIED: executed experiments, 2026-11-21] |
| `pandas` | 3.1.1 (PyPI 2026-11-04) | Hard import of `mlflow.genai.evaluation.harness` (`import pandas as pd`, harness.py:15); `mlflow-skinny` does not depend on it | `ModuleNotFoundError: No module named 'pandas'` reproduced under skinny alone; adding pandas fixed it [VERIFIED: executed] |
| `ghcr.io/mlflow/mlflow` | tag `v3.18.0`, index digest `sha256:257204c77980b0f3450a26eb6089e487603fcdd4509529eadaf88f90669f5c13` | MLflow server container (UI + REST + SQLite + artifact proxy) | Official image; its Dockerfile is `pip install mlflow==$VERSION` on `python:3.11-slim-trixie`; contents confirmed: mlflow 3.18.0, SQLAlchemy 2.1.8, uvicorn 0.54.0 [VERIFIED: `docker buildx imagetools inspect`, `docker run`] |
| Existing pins (unchanged) | langgraph 1.2.20, anthropic 2.6.0, fastmcp 4.1.6, pydantic 2.14.2, PyYAML 6.0.3 | Reused through `buddy_bot`, `buddy_core` | [VERIFIED: services/chat_bot/requirements.txt, requirements-dev.lock] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `numpy` (transitive of pandas) | 2.5.5 | Locked automatically | Appears in `jobs/eval/requirements.lock` |
| `langchain` (extra) | not needed | `mlflow.langchain.autolog()` worked with only `langchain-core 1.8.0` (already a langgraph dependency) | Do NOT add `mlflow[langchain]` [VERIFIED: executed with `langchain` absent] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `mlflow-skinny` + `pandas` | full `mlflow==3.18.0` in the eval image | Simpler single pin, but +550 MB, drags sqlalchemy/flask/scipy/sklearn into the test image and dev lock; only needed if the eval client itself must open a SQLite store (it does not: it talks HTTP to the server) |
| Official MLflow image by digest | A project-built `mlflow_server` Dockerfile stage with a hashed lock | Matches repo conventions (python 3.12, uid 10001, `--require-hashes`) and fixes the root-volume problem, but costs a new lock + stage + structural tests. Choose it only if root-in-container is unacceptable (see Open Question 2) |
| `mlflow.genai.evaluate(data=traces)` | Own scoring loop + `mlflow.log_feedback` | Both verified to exist. Evaluate gives the Evaluation-run view and aggregated `scorer/mean` metrics for free; `log_feedback` avoids duplicate assessments on re-score. See "Re-score duplicates" pitfall |

**Installation (jobs/eval/requirements.txt, new pins, both need a human-verify checkpoint):**
```text
mlflow-skinny==3.18.0
pandas==3.1.1  # required by mlflow.genai.evaluate harness; not a dependency of mlflow-skinny
```
Then add `-r jobs/eval/requirements.txt` to `requirements-dev.txt` and run `scripts/lock-requirements.sh` (extend it with `compile_stage jobs/eval/requirements.lock requirements.txt services/chat_bot/requirements.txt jobs/eval/requirements.txt`).

**Version verification (executed 2026-11-21):**
```bash
curl -s https://pypi.org/pypi/mlflow-skinny/json   # 3.18.0, upload 2026-11-03T23:32:43; requires_python >=3.10
curl -s https://pypi.org/pypi/pandas/json          # 3.1.1,  upload 2026-11-04T15:05:30; first upload 2009-12-25
docker manifest inspect ghcr.io/mlflow/mlflow:v3.18.0   # amd64 + arm64 manifests exist
```
A dry-run resolve of `requirements-dev.txt + mlflow-skinny==3.18.0 + pandas==3.1.1` on python 3.12 succeeds (137 packages). Side effect: `cachetools` moves from the dev lock's 8.0.0 to 7.3.3 (mlflow-skinny requires `cachetools<8`) and `python-multipart` 0.0.33 to 0.0.34, so regenerating the locks changes the shared dev lock and every stage lock [VERIFIED: pip dry-run report; the first attempt with the old lock as constraints failed with "mlflow-skinny 3.18.0 depends on cachetools<8 and >=5.0.0 / The user requested (constraint) cachetools==8.0.0"].

**Declared compatibility (MLflow 3.18.0 `ml-package-versions.yml`)** [CITED: raw.githubusercontent.com/mlflow/mlflow/v3.18.0/mlflow/ml-package-versions.yml]: langchain 1.0.4 to 1.4.7; anthropic autologging 0.72.1 to 2.2.0; langgraph 1.0.3 to 1.2.16. This repo pins anthropic 2.6.0 and langgraph 1.2.20, both **above** MLflow's tested maximum. Behaviour was verified empirically (below), so the risk is regression on a future bump, not a current failure. Pin exact versions and re-run the eval smoke on any bump.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `mlflow-skinny` | PyPI | first upload 2018 (family; `mlflow` first upload 2018-06-04), latest release 18 days | `mlflow` 5.8M/week (pypistats, `mlflow-skinny` not queried) | github.com/mlflow/mlflow (PyPI `project_urls`; the seam reported `repoUrl: null`) | SUS (seam reasons: `too-new`, `unknown-downloads`, `no-repository`) | Flagged: planner must add `checkpoint:human-verify` before install. Evidence for the human: same Databricks-maintained project as `mlflow`; sdist+wheel from the same release workflow; the "too-new" signal is the latest release date, not package age |
| `pandas` | PyPI | first upload 2009-12-25, latest release 17 days | not queried | github.com/pandas-dev/pandas (not read from registry this session) | SUS (same three seam reasons) | Flagged: planner must add `checkpoint:human-verify` before install. pandas is already a transitive dependency of the official MLflow image |
| `mlflow` (full) | PyPI | 2018-06-04 | 5.8M/week | github.com/mlflow/mlflow | SUS (same reasons) | Not recommended (see Alternatives); only used inside the third-party server image |
| `numpy` | PyPI | transitive | - | - | not checked | Transitive of pandas; lock-pinned with hashes by the lock script |
| `ghcr.io/mlflow/mlflow` | GHCR image | v3.18.0 | - | github.com/mlflow/mlflow | n/a (image, not a pip package) | Approved; pin by index digest, treat tag as informational |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** `mlflow-skinny`, `pandas` (and `mlflow`, unused): planner inserts `checkpoint:human-verify` before the first install. The seam's SUS reflects heuristics (`too-new` keyed to the newest release, no downloads data, no repo URL in its payload), not a registry anomaly: `npm`-style postinstall scripts do not exist on PyPI. `pip index versions`/PyPI JSON confirm both exist on the correct registry.

*Package names above were confirmed from MLflow's own documentation/source and PyPI JSON in this session; the `[VERIFIED]` status of each still depends on the human checkpoint required by the SUS verdict.*

## Architecture Patterns

### System Architecture Diagram

```
                       (host, once per refresh)
 Guides repo --guides-index--> GUIDES_INDEX.md  (the owner commits)   handbook snapshot (private)
        |                                                                |
        +----------- compose `sync` one-shot (existing) -----------------+
                                   |  writes index.db + manifest
                                   v
                          volume `artifacts` (ro)
                    +--------------+---------------+
                    v                              |  (also ro, read by eval for source-id resolution + index hash)
        mcp-server :8000  <--- MCP HTTP ---+       |
        (real index, Firestore gaps)       |       |
                                           |       |
 fixture sources --eval-fixture one-shot-> volume `eval-empty` (ro)
 (committed .md)            v              |
        mcp-server-empty :8000 <-----------+       |
                                           |       |
 docs/internal/golden-handbook.yaml (ro) --+       |
 jobs/eval/golden/guides.yaml (in image)   |       |
                                           v       v
                        +-------------- eval container (buddy_eval) ---------------+
   CLI: lint | preflight | recall | run | empty-context | gate
                        |                                                          |
  golden loader -> cache lookup (item+index+bot+models hash) --hit--> outcome+trace_id
                        | miss                                                      |
                        v                                                           |
   COLLECT: @mlflow.trace bot_run -> run_workflow(question, [], deps) ------------- |
        |   (LangGraph autolog: node spans; Anthropic autolog: LLM spans)           |
        |   -> BotReply(kind, answer, sources[text], referente, gap_reported)       |
        |   -> log_expectation(trace) ; cache {outcome, trace_id}                   |
        v                                                                           |
   SCORE: deterministic rules (kind, citation, role, gap) + ONE judge call/item     |
        |   (Opus via LlmClient.structured, cached verdict)                         |
        |   mlflow.genai.evaluate(data=[Trace...], scorers=[correctness,citation,   |
        |   invented_policy])  -> assessments on the same traces                    |
        v                                                                           |
   GATE: pure function -> PASS/FAIL + failing metrics + exit code; JSON report      |
        +------+-------------------+------------------+----------------------------+
               v                   v                  v
        meridian :3456      mlflow :5000        Firestore emulator :8080
        (Max session)       (SQLite + artifacts  (gap documents)
                             volume; UI on
                             127.0.0.1:5000)
```

### Recommended Project Structure
```
jobs/eval/
├── README.md
├── requirements.txt / requirements.lock
├── golden/guides.yaml               # committed: Guides + no-answer + no-rule sensitive items; NO handbook:// anywhere
├── fixtures/empty_context/          # committed markdown sources of the unrelated fixture index
└── buddy_eval/
    ├── __main__.py, cli.py          # subcommands: lint preflight recall run empty-context gate build-fixture
    ├── config.py                    # EvalSettings (pydantic-settings, errors name variables, never values)
    ├── golden.py                    # GoldenItem model, loader (public + private merge), lint
    ├── sources.py                   # source_url -> chunk_key resolver over the read-only index; expected-source matching
    ├── cache.py                     # per-item JSON cache; key = sha256(item, index hash, bot version, model ids, judge version)
    ├── runner.py                    # collect phase: one item through run_workflow, error classification
    ├── judge.py                     # JudgeVerdict schema, prompt, call via LlmClient
    ├── scoring.py                   # PURE rules: correctness/citation/role/gap per kind; invented count
    ├── recall.py                    # Recall@5 (hit-any primary, fractional secondary)
    ├── empty_context.py             # run answerable items against mcp-server-empty
    ├── gate.py                      # PURE: metrics -> verdict
    ├── tracing.py                   # the ONLY module importing mlflow: autolog, traced wrapper, expectations, evaluate
    ├── report.py                    # console table + JSON (links to traces)
    └── fixture.py                   # build_index() of the empty-context fixture
tests/unit/buddy_eval/               # hermetic: FakeLlm, in-process FastMCP, fake tracing sink
scripts/eval-smoke.sh                # compose + stub LLM + MLflow, asserts traces and verdict
```

### Pattern 1: Reuse the bot through its ports, do not copy it
**What:** `run_workflow(question, [], WorkflowDeps(llm, connector, config))` is the predict entry; `FastMcpConnector("http://mcp-server:8000/mcp")` is the real adapter; `build_llm_client` builds the real LLM client. `BotReply` already carries everything the scorer needs.
**Evidence** (verbatim):
- `workflow.py:292`: `async def run_workflow(question: str, history: Sequence[Turn], deps: WorkflowDeps) -> BotReply:` [VERIFIED: Read]
- `schemas.py:78-83`: `kind: Literal["answer", "refusal", "referral", "smalltalk", "error"]`, `answer: str = ""`, `sources: list[Evidence] = Field(default_factory=list)`, `referente: Referente | None = None`, `gap_reported: bool = False`, `gate_reason: str | None = None` [VERIFIED: Read]
- `schemas.py:8-19`: `Evidence` has `source_url`, `kind`, `title`, `text`, `revision_date`, `revision_kind`, `video_url` [VERIFIED: Read]
- `workflow.py:209-218` (`finish`): `reply = BotReply(kind="answer", answer=draft.answer, sources=cited_sources(state["evidence"], draft), referente=await _referente(state, runtime.context) if sensitive else None,)` so cited sources with **full tool text** are on `reply.sources`: no State seam is needed for the invented-policy judge (D-10) [VERIFIED: Read]
- `workflow.py:221-229` (`refuse`): `kind="referral" if sensitive else "refusal"`, referente always set [VERIFIED: Read]
- `workflow.py:289,302`: `return reply.model_copy(update={"gap_reported": True})` inside `_log_gap`, called only `if reply.kind in ("refusal", "referral"):` [VERIFIED: Read]

**Consequence for the gap signal (question 6):** `gap_reported` is set only after `tools.report_gap` returned a validated `GapReportOutput` (`status: Literal["recorded"]`, models.py:118) and `buddy_report_gap` returns only after `await gaplog.record(gap)` completed (gap_tool.py). So `reply.gap_reported` is a sound deterministic signal for "a gap was logged"; a Firestore query is optional corroboration. An independent cross-check (document-count delta through the emulator REST endpoint that `services/chat_bot/README.md` documents) is cheap and worth adding to `empty-context` because D-16 says "a gap is logged for each" [VERIFIED: gap_tool.py, gaplog.py, models.py reads].

**Consequence for the Recall reformulation (question 6):** the node `reformulate` can be called directly: `await reformulate({"question": q, "history": []}, Runtime(context=RunContext(llm=..., tools=None, config=cfg)))` returns `{"reformulation": Reformulation(...)}` (or `{"reply": BotReply(kind="error")}` on `LlmError`). Executed: `langgraph.runtime.Runtime(context=ctx)` constructs with keyword-only defaults and the node ran, including `_known_topic_only` normalisation. So Recall uses the **identical** prompt, model and post-processing as the bot without touching bot code [VERIFIED: executed].

### Pattern 2: Collect, then evaluate over traces (recommended resolution of D-14 x D-20)
**What:** Phase 1 runs the bot inside one MLflow run with a traced wrapper and stores `{outcome, trace_id}` in the item cache. Phase 2 calls `mlflow.genai.evaluate(data=<list of Trace>, scorers=[...])`; scorers get `outputs` (the wrapper's return value), `expectations` (logged on the trace), and read the judge verdict from the local cache.
**When to use:** always for this phase; it is the only design in which cached reruns still point at a trace with real spans.
**Example (executed against the real graph, skinny 3.18.0, official server image):**
```python
# Source: executed experiment exp4/exp5, 2026-11-21 (mlflow-skinny 3.18.0, langgraph 1.2.20, anthropic 2.6.0)
import mlflow, asyncio
import mlflow.langchain, mlflow.anthropic          # autolog flavours
from mlflow.entities import Feedback
from mlflow.genai.scorers import scorer

mlflow.set_tracking_uri("http://mlflow:5000")      # env MLFLOW_TRACKING_URI also works
mlflow.set_experiment("ai-buddy-eval")
mlflow.langchain.autolog()                         # one span per LangGraph node + router spans
mlflow.anthropic.autolog()                         # LLM-call spans (AsyncMessages.create, CHAT_MODEL)

@mlflow.trace(name="bot_run")                      # root span: keeps LLM spans in the SAME trace (see Pitfall 4)
async def bot_run(question: str) -> dict:
    reply = await run_workflow(question, [], deps)  # deps built INSIDE (fresh async clients per call)
    return reply.model_dump(mode="json")

with mlflow.start_run(run_name="collect") as run:
    asyncio.run(bot_run(item.question))
    trace_id = mlflow.get_last_active_trace_id()
    mlflow.log_expectation(trace_id=trace_id, name="expected_sources", value=item.expected_sources)
    mlflow.log_expectation(trace_id=trace_id, name="key_facts", value=item.key_facts)

traces = mlflow.search_traces(run_id=run.info.run_id, return_type="list")   # or [mlflow.get_trace(i) for i in ids]

@scorer
def citation(outputs, expectations) -> Feedback:    # deterministic; params are chosen by name
    cited = [s["source_url"] for s in outputs["sources"]]
    ok = any(c in expectations["expected_sources"] for c in cited)
    return Feedback(value=ok, rationale=f"cited={cited}")

result = mlflow.genai.evaluate(data=traces, scorers=[citation])   # no predict_fn in this mode
```
Observed: 12 spans per trace (`bot_run` root; `LangGraph`; `reformulate`, `_after_reformulate`, `retrieve`, `_after_retrieve`, `answer`, `gate`, `_decide`, `finish`; two `AsyncMessages.create` LLM spans), assessments `expected_sources`, `key_facts`, scorer feedback all on the original trace, and exactly 4 stub-LLM requests for 2 items (no hidden extra call) [VERIFIED: executed; stub request counter].

### Pattern 3: Pure core, thin MLflow shell (Ports & Adapters)
`scoring.py`, `gate.py`, `recall.py`, `cache.py`, `golden.py` import no mlflow. `tracing.py` is the single adapter (a `TraceSink`-style Protocol with a fake for unit tests). The `@scorer` wrappers are 3-line adapters over the pure functions. This keeps `./run-unit-tests.sh --all` offline (`--network none`) and fast, and confines the one third-party API surface that moves between MLflow releases [CITED: DESIGN_PATTERNS_GUIDE §9 Hexagonal; MLFLOW_GENAI_GUIDE §12 "Deterministic checks belong here, not in a judge"].

### Pattern 4: Deterministic scoring rules per item kind (D-09 made concrete)
Derived from the workflow's actual branches (`finish` yields `kind="answer"` and, when `sensitive_topic` is set, `referente`; `refuse` yields `refusal` or `referral`):

| Item kind | Correct iff (deterministic part) | Judge part |
|-----------|---------------------------------|------------|
| `handbook` / `guides` | `kind == "answer"` and `{s.source_url for s in sources}` resolves to at least one `expected_sources` entry | every `key_fact` present, none contradicted |
| `no_answer` | `kind == "refusal"` and `gap_reported` | none |
| `sensitive`, rule exists | `kind == "answer"`, `referente.role == expected_referente_role`, cited source matches `expected_sources` | key_facts present (the rule) |
| `sensitive`, no rule | `kind == "referral"`, `referente.role == expected_referente_role`, `gap_reported` | none |
| any kind | `kind in {"smalltalk","error"}` is **never** a model verdict: classify `error` as `errored` (infrastructure) and fail the run as incomplete, do not count it as a wrong answer and do not cache it | - |

Invented-policy judge runs on **every** item with `kind == "answer"` (D-10), including no-answer items that wrongly answered. One structured judge call per answered item returns facts and invented claims together (so `correctness` and `invented_policy` scorers share one cached call); refusals cost no judge call.

### Anti-Patterns to Avoid
- **`predict_fn` that short-circuits on a cache hit:** emits a trace with no spans (EVAL-05 broken on reruns). Use Pattern 2.
- **Letting `evaluate` run the sample-validation call:** it executes `predict_fn` once with the first dataset row (real LLM calls, gap writes) before the run. Set `MLFLOW_GENAI_EVAL_SKIP_TRACE_VALIDATION=true` if `predict_fn` mode is ever used.
- **Building `AsyncAnthropic`/`FastMcpConnector` once and reusing them across `asyncio.run` calls:** MLflow's async wrapper calls `asyncio.run` per row (new loop each time) and scorer threads need their own loops. Create clients inside the coroutine.
- **Copying handbook text into committed files, the cache, or logs:** see Don't Hand-Roll and Security.
- **Importing `mlflow` in the bot packages** (D-18): the `chat_bot` image must stay mlflow-free (`test_chat_bot_stage_disables_tracing` and `LANGSMITH_TRACING` guard exist; do not weaken them).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Trace storage/UI, span capture per graph node | Custom tracer port or JSON logging | `mlflow.langchain.autolog()` | Verified node-level spans on langgraph 1.2.20; D-19's fallback port is **not needed** |
| LLM call spans | Wrapper around `LlmClient` | `mlflow.anthropic.autolog()` plus a `@mlflow.trace` root | Verified; LLM spans land in the same trace only with the root wrapper |
| Per-run aggregation of scorer means | Own mean/percent code for MLflow metrics | `mlflow.genai.evaluate` run metrics (`<scorer>/mean`) for the UI; **gate numbers come from the pure `gate.py` over the local cache** | UI numbers are informative; the gate must be deterministic and unit-testable |
| YAML parsing/validation | `yaml.load`, manual dict checks | `yaml.safe_load` + pydantic model with `extra="forbid"` | Repo already pins PyYAML and pydantic; typos in field names must fail loudly |
| Index reading, source resolution | SQL against `index.db` | `buddy_core.index_reader.open_index` / `IndexReader.guide_chunks()` and `.meta` | The reader is the only SQL surface (index_reader.py docstring); `meta` has `content_hash`, `guides_commit_sha`, `build_id` |
| Empty-context fixture index | Hand-written SQLite | `buddy_core.index_writer.build_index(IndexContent(...), dest, now=...)` | Same schema/FTS rebuild/`user_version` the server validates |
| Guides index regeneration + drift check | New script | `python -m buddy_sync guides-index --checkout DIR` and `run --strict` (cli.py:142,174) | Already shipped (D-23) |
| Retry/backoff against rate limits | Custom loops per call | Fail the item as `errored`, stop after N consecutive errors, resume from cache | Re-running is free by design (D-14); infinite retry burns Max quota |

**Key insight:** the expensive, error-prone parts (graph, gate, retrieval, index schema, tracing) already exist. Phase 5 is orchestration, scoring rules, and measurement hygiene; the risk is in measurement hygiene (hollow traces, duplicate feedback, stale index, cache invalidation), not in algorithms.

## Runtime State Inventory

Not a rename/refactor/migration phase. Omitted. (Phase 5 adds state: the MLflow volume, the eval cache and reports, the empty-context fixture volume; their privacy handling is in Security Domain.)

## Common Pitfalls

### Pitfall 1: `mlflow.genai.evaluate` makes an extra real call and uses 10 threads
**What goes wrong:** with the default settings it runs `predict_fn` once on the first row "to check it emits a trace" (executed: 6 stub-LLM requests for 2 rows instead of 4) and evaluates rows/scorers with `MLFLOW_GENAI_EVAL_MAX_WORKERS=10` / `MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS=10` (defaults read from `environment_variables.py:938,946`).
**Why:** the harness validates traces before the run; defaults assume cheap model calls.
**How to avoid:** Pattern 2 (no `predict_fn`) removes the extra call; still set `MLFLOW_GENAI_EVAL_MAX_WORKERS=1` and `MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS=1` (D-14 sequential, and it removes the race where two scorers sharing one cached judge call both miss the cache). If `predict_fn` mode is used anywhere: `MLFLOW_GENAI_EVAL_SKIP_TRACE_VALIDATION=true` plus `@mlflow.trace`.
**Warning signs:** stub/Meridian request counter higher than items x calls-per-item.

### Pitfall 2: Trace writes are asynchronous; `log_expectation` right after a run fails
**What goes wrong:** `mlflow.log_expectation(...)` raised `RESOURCE_DOES_NOT_EXIST: Trace with ID 'tr-...' not found` immediately after the traced call.
**Why:** traces are exported on a background queue (`MLFLOW_ENABLE_ASYNC_TRACE_LOGGING` default True, environment_variables.py:1340).
**How to avoid:** set `MLFLOW_ENABLE_ASYNC_TRACE_LOGGING=false` in the eval container (executed: fixes it), or call the flush API before logging assessments. Guide §28 #27 notes the async queue can also drop traces under load, irrelevant at 1 trace per item but another reason to disable it.
**Warning signs:** `RestException ... not found` right after a run; fewer traces than items.

### Pitfall 3: Default MLflow server rejects the compose service name (403) while `/health` stays 200
**What goes wrong:** from another container, `http://mlflow:5000/api/2.0/mlflow/experiments/search` and `/` returned `403 Invalid Host header - possible DNS rebinding attack detected` with default flags; `/health` returned 200, so a healthcheck passes while every client call fails.
**Why:** MLflow 3.x security middleware allows only localhost and private IPs by default (`--help`: "Default allows: localhost (all ports), private IPs"), and a service name is neither.
**How to avoid:** `--allowed-hosts "mlflow:5000,localhost:*,127.0.0.1:*"` (executed: all three paths return 200 from the sibling container). Guide §24 documents the same error and flag, and that it works only with the default uvicorn server, not under `--gunicorn-opts`/`--waitress-opts`: keep the default. Healthcheck an API path, not `/health`, or add a smoke assertion that lists experiments.
**Warning signs:** `Invalid Host header` in client output.

### Pitfall 4: Anthropic autolog spans become stray traces unless a root span is active
**What goes wrong:** with only autolog (no `@mlflow.trace` root), the LangGraph run is one trace but **each LLM call is a separate single-span trace** (executed: 6 traces for 2 items: 2 LangGraph traces + 4 `AsyncMessages.create` roots). The "generation" prompt/response would not be attached to the item.
**Why:** the LangChain callback tracer creates its spans without making them the active OpenTelemetry context, so the raw Anthropic SDK call inside a node finds no parent.
**How to avoid:** wrap the call in `@mlflow.trace(name="bot_run")`; executed result: one trace per item, LLM spans are children of `bot_run` (siblings of the `LangGraph` subtree, not nested under their node span). Also keep `mlflow.anthropic.autolog()` **disabled during the score phase** so judge calls do not create their own stray traces (not executed: [ASSUMED] that evaluate-over-traces would otherwise trace judge calls).
**Warning signs:** trace count > item count.

### Pitfall 5: Re-running `mlflow.genai.evaluate` on the same traces appends duplicate feedback
**What goes wrong:** a second evaluate over the same traces added a second `has_citation` assessment to each trace (executed: assessments list showed it twice, both `valid=True`).
**Why:** assessments are append-only unless overridden.
**How to avoid:** the gate/report read verdicts from the **local cache**, not from MLflow; call `evaluate` only for items whose scores are not yet attached for the current cache key (store `scored_trace_ids` in the cache), or use `mlflow.log_feedback` once per (trace, scorer). Do not build the gate on `result_df` or the UI.
**Warning signs:** two identical scorer names on one trace.

### Pitfall 6: MLflow server image runs as root; non-root + fresh named volume fails
**What goes wrong:** `--user 10001:10001` with an empty named volume: `sqlite3.OperationalError: unable to open database file`, and the container stays `Up` (workers loop) instead of exiting, so the healthcheck is the only signal. Image facts: `Config.User` empty, entrypoint none, `CMD [python3]`, Python 3.11.18, size 1.34 GB, no `curl`.
**How to avoid:** run as root with `cap_drop: [ALL]` and `security_opt: [no-new-privileges:true]` (executed: starts, serves, creates `/mlflow/mlflow.db` on the named volume), bind the published port to loopback only, and use a Python-based healthcheck (`python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/2.0/mlflow/experiments/search?max_results=1')"`; the Python `urllib` pattern is the one `mcp-server` already uses in this compose file). If root is rejected, build a project stage instead (Alternatives).
**Warning signs:** `mlflow` service `Up` but unhealthy.

### Pitfall 7: Rate limiter on `mcp-server` throttles a tight Recall loop
**What goes wrong:** `RATE_LIMIT_RPS=5`, `RATE_LIMIT_BURST=30`; all unauthenticated callers share the `anonymous` bucket and "Over the limit the reply is HTTP 200 with a JSON-RPC error, not HTTP 429" (services/mcp_server/README.md "Rate limiting"). Opening one session per item costs `initialize` plus tool calls (about 3 requests): 28 items cached-reformulation recall = about 84 requests in a few seconds, past the burst, producing `McpToolError` per item that looks like a retrieval failure.
**How to avoid:** pace the recall loop (>= 0.25 s between sessions) or reuse one session for all items; make `McpToolError` a loud run error, never a recall miss; Recall must distinguish "tool returned no results" from "tool call failed". The live bot sharing the same `mcp-server` shares the bucket.
**Warning signs:** `returned no structured result` errors clustered after the first ~10 items.

### Pitfall 8: Unhandled `LlmUnavailableError` crashes the run mid-item
**What goes wrong:** `answer` catches only `LlmOutputError` (`workflow.py:183`) and `retry_plan` likewise (`:163`); an `LlmUnavailableError` (Meridian 429/5xx/timeout, mapped in `llm.py:110-112`) propagates out of `ainvoke` and `run_workflow` raises. `reformulate` is different: it catches `LlmError` and returns `BotReply(kind="error")` (`:102-106`).
**How to avoid:** the runner catches `LlmError` and `McpToolError` per item, records `errored` (never cached), aborts after N consecutive errors with a "resume with the same command" message. The gate treats any `errored` item as "incomplete run" FAIL, not as a wrong answer.
**Warning signs:** traceback out of `run_workflow`; many `kind="error"` replies.

### Pitfall 9: Cache invalidation must include the right inputs
**What goes wrong:** a stale cached outcome survives a prompt/code change or an index refresh, and the gate reports a pass the current bot would not earn.
**How to avoid:** key = sha256 over (golden item JSON, index `content_hash`, `guides_commit_sha`, bot version, `reformulate_model`, `answer_model`, `judge_model`, judge prompt/schema version, eval scoring version). Recommended bot version: hash of all `services/chat_bot/buddy_bot/*.py` plus `packages/buddy_core/buddy_core/data/escalation_topics.yaml` read at runtime (any edit invalidates; conservative is correct). Separate cache namespaces: `reformulation` (key: question + model + prompt hash), `outcome`, `verdict`. Never cache `errored` results. `index.manifest.json` carries `content_hash`; `open_index(...).meta` carries `content_hash`, `guides_commit_sha`, `build_id`.

### Pitfall 10: Empty-context fixture overlap gives false FAIL (or a meaningless PASS)
**What goes wrong:** retrieval is OR-of-tokens FTS (`to_match_query` joins tokens with ` OR `, index_reader.py), so a fixture sharing any stemmed word with a question returns evidence, the answer step runs, and the test can fail (or, with a stub that cites any returned evidence, "answer"). Conversely a fixture that is too thin may trip cold-start guards.
**How to avoid:** fixture content in vocabulary disjoint from both Italian office life and the Guides domain (for example mycology or celestial mechanics, written in English and Italian with no stopword-heavy prose); at least one handbook page and one Guides chunk; a `build-fixture`/`lint` step that reports, per golden question, whether the fixture `handbook_search`/`guides_search` returned anything (informational, run locally because handbook questions are private). The deterministic unit variant must use a scripted `FakeLlm` with chosen keywords, not `stub_llm.py` (the stub derives keywords from every 4+ letter word of the question, including stopwords, which can match).

### Pitfall 11: Meridian specifics for Opus (unverified)
Meridian docs (commit `cafdcf7`, `docs/configuration.md`, first 100 000 of 148 997 characters read) state: "Fable and Opus tiers: Both default to their `[1m]` variants", opt out with `MERIDIAN_OPUS_MODEL=opus`; Sonnet's 1M tier "requires Extra Usage"; `MERIDIAN_MAX_CONCURRENT` default 10; requests on one session are serialized; queue-capacity failures answer "503 `overloaded_error`". It does **not** document how an arbitrary requested id such as `claude-opus-5-5` maps to a tier, nor any Max-plan limit numbers. See Open Question 1 and A2/A3.

### Pitfall 12: Touching `services/chat_bot` triggers the chat-bot CI workflow
`tests/unit/test_workflows.py` asserts `("services/chat_bot/buddy_bot/service.py", {"chat-bot.yml"})`: any edit under `services/chat_bot` (for example typing `build_llm_client`) runs the chat-bot pipeline on push. Acceptable, but expect it, and keep bot edits to the minimum (Open Question 3).

## Code Examples

### Hermetic in-process MCP for unit tests (existing pattern to copy)
```python
# Source: tests/unit/chat_bot/conftest.py (read this session)
connector = RecordingConnector(FastMcpConnector(mcp_server))   # mcp_server = build_server(...) over write_index(tmp, make_content())
deps = WorkflowDeps(llm=FakeLlm({Reformulation: [...], AnswerDraft: [...]}), mcp=connector, config=workflow_config)
```
Note: with an in-process FastMCP the SQLite snapshot belongs to the loop thread; keep unit tests on one event loop (pytest anyio, as the existing tests do), never inside MLflow's worker threads.

### Source-id resolution (guides permalinks to stable chunk keys)
Guides `source_url` is `f"{web_base}/blob/{commit_sha}/{path}#{anchor}"` with `anchor = f"L{start}"` or `f"L{start}-L{end}"` (guides_tools.py:49 and the lines above it) [VERIFIED: Read]; handbook is `f"handbook://{page_id}"` (handbook_tools.py:35) [VERIFIED: Read]. Line numbers shift on every Guides edit, so goldens must **not** store permalinks. Store the stable chunk key `file#h2slug/h3slug/part` (buddy_core `make_chunk_key`), usually without the `/part` suffix so any part of the section matches. Resolve at run time:
```python
# Source: derived from guides_tools.py + buddy_core.index_reader (design, executed pieces: open_index/meta)
_PERMALINK = re.compile(r"/blob/[0-9a-f]{40}/(?P<path>[^#]+)#L(?P<a>\d+)(?:-L(?P<b>\d+))?$")
by_span = {(c.file, c.line_start, c.line_end): c.chunk_key for c in reader.guide_chunks()}
def to_key(source_url: str) -> str | None:
    if source_url.startswith("handbook://"):
        return source_url
    m = _PERMALINK.search(source_url)
    return by_span.get((unquote(m["path"]), int(m["a"]), int(m["b"] or m["a"]))) if m else None
```
This needs the artifacts volume mounted read-only in the eval container (it already is read-only for `mcp-server`; same pattern). The sync stage `chunk_key` is derived from redacted headings; lint must re-validate every golden `expected_sources` entry against the **current** index and fail on a missing key.

### Compose service for MLflow (all flags exercised in experiments)
```yaml
# Source: executed with docker run (same flags); compose wrapper is design
  mlflow:
    profiles: [eval]
    image: ghcr.io/mlflow/mlflow:v3.18.0@sha256:257204c77980b0f3450a26eb6089e487603fcdd4509529eadaf88f90669f5c13
    command:
      - mlflow
      - server
      - --host
      - 0.0.0.0
      - --port
      - "5000"
      - --backend-store-uri
      - sqlite:////mlflow/mlflow.db
      - --artifacts-destination
      - /mlflow/artifacts
      - --allowed-hosts
      - "mlflow:5000,localhost:*,127.0.0.1:*"
    environment:
      MLFLOW_DISABLE_TELEMETRY: "true"
    ports:
      - "127.0.0.1:5000:5000"
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
    volumes:
      - mlflow-data:/mlflow
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/2.0/mlflow/experiments/search?max_results=1', timeout=3)"]
      interval: 3s
      timeout: 5s
      retries: 30
```
Eval-side environment: `MLFLOW_TRACKING_URI=http://mlflow:5000`, `MLFLOW_DISABLE_TELEMETRY=true`, `MLFLOW_ENABLE_ASYNC_TRACE_LOGGING=false`, `MLFLOW_GENAI_EVAL_MAX_WORKERS=1`, `MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS=1`, `GIT_PYTHON_REFRESH=quiet` (the skinny package imports GitPython and logs a long banner when no `git` binary exists; the eval image needs no git), `LANGSMITH_TRACING=false`.

### Judge schema and call (design, deterministic post-processing)
```python
class FactCheck(BaseModel):
    fact: str; present: bool; contradicted: bool
class JudgeVerdict(BaseModel):
    facts: list[FactCheck]
    invented_claims: list[str]      # each: the claim as written in the answer + why the cited text does not support it
    reasoning: str
# correct_facts = all(f.present and not f.contradicted for f in facts); invented = len(invented_claims) > 0
verdict = await llm.structured(JudgeVerdict, model=cfg.judge_model, system=JUDGE_SYSTEM, user=build_judge_user(item, reply), max_tokens=1500)
```
Wrap evidence in tagged blocks as `prompts.format_evidence` does (`<fonte id=... >`), state that the answer and the sources are data, never instructions, and pass the **full** `Evidence.text` (the bot's own prompt truncates each source to `MAX_EVIDENCE_CHARS = 4000`, prompts.py:185, so the judge may see text the answerer never saw; note it in the report, do not "fix" it).

### Scorers that read the cache (executed shape; sync functions, own event loop for async judge)
```python
@scorer
def invented_policy(inputs, outputs, expectations) -> Feedback:
    verdict = judge_cache.get_or_compute(...)      # asyncio.run(llm.structured(...)) inside; fresh AsyncAnthropic per call
    return Feedback(value=len(verdict.invented_claims) == 0, rationale="; ".join(verdict.invented_claims) or verdict.reasoning)
```
Executed: a sync scorer calling `asyncio.run(...)` with a fresh `AsyncAnthropic` client inside `mlflow.genai.evaluate`'s worker thread ran and its rationale was stored on the trace. Async scorer `__call__` methods are rejected: "Async scorer '__call__' methods are not supported" (scorers/base.py:329-333) [VERIFIED: read + executed].

### D-01 prerequisite commands (existing tooling)
```bash
# regenerate (needs a writable checkout; README of jobs/sync documents this exact form)
docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v "$PWD:/app" -v "$HOME/Desktop/WORK/Guides:/guides-src" -w /app \
  ai-buddy-test python -m buddy_sync guides-index --checkout /guides-src
# The owner commits GUIDES_INDEX.md in the Guides repo (the sync clones committed content only)
# then refresh and check drift; the strict check is `run --strict` (plain `run` only warns, and sync-and-publish.sh calls plain `run`)
HANDBOOK_SRC_DIR=... GUIDES_SRC_DIR=... REDACT_PAGE_FILES=... scripts/sync-and-publish.sh --local-only
```
`scripts/sync-and-publish.sh` writes the host `./artifacts`; the **compose** stack serves the named volume `artifacts` built by the compose `sync` one-shot, so the compose `sync` must be re-run too (`docker compose run --rm sync` with the same three variables) before Recall/scoring. Current local index (built 2026-11-16): 22 handbook pages, 2798 chunks over 17 Guides files, `guides_commit_sha` `91aa3f63...` (the Guides repo is now at `4526500`), which confirms D-01's staleness [VERIFIED: sqlite read of `artifacts/index.db`, `git log` in Guides].

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `mlflow.evaluate` / `evaluator_config` | `mlflow.genai.evaluate(data, scorers, predict_fn, model_id[, quality_criteria])`; guide §28 #2 says passing `evaluator_config`/`model_type` raises `TypeError` | MLflow 3.x | Signature is exactly as in the 3.18.0 source read this session (`quality_criteria` experimental, added 3.18.0; not used, the gate is custom) |
| Sync-only `predict_fn` | `async def predict_fn` auto-wrapped with `asyncio.run` and a timeout (`MLFLOW_GENAI_EVAL_ASYNC_TIMEOUT`, default 300 s) | current 3.x | D-20's async question: **supported** [VERIFIED: base.py:294, trace_utils.py:609; executed] |
| `file:` store, `./mlruns` | SQL backend required for traces/datasets (guide §28 #1, §24) | 3.x | SQLite on a volume satisfies D-21 |
| MLflow security defaults | DNS-rebinding host check on by default in the server | 3.x | Pitfall 3 |
| Usage telemetry | On by default; off with `MLFLOW_DISABLE_TELEMETRY=true` or `DO_NOT_TRACK=true` (telemetry/utils.py:154-155) | 3.x | Must be disabled on both client and server in this private setting |

**Deprecated/outdated:** `ragas.evaluate()` and RAGAS legacy metric imports (RAG guide §21); not used. `mlflow[genai]` extra is for gateway/cost (guide §28 #32), not needed.

## Guides Applied (D16: exact sections and exceptions)

Guides checkout `4526500`; file paths are repo-relative to `~/Desktop/WORK/Guides`.

| Guide / section | Applied as |
|-----------------|-----------|
| `AI-Engineering/MLFLOW_GENAI_GUIDE.md` §3 Setup, §24 Self-Hosting | SQL backend (SQLite), `--allowed-hosts` for the service name, default uvicorn server, no archival config, local volume only |
| §5 Tracing in Depth, §6 Automatic Tracing | `mlflow.langchain.autolog()` + `mlflow.anthropic.autolog()`, `@mlflow.trace` root, tags/metadata per item |
| §10 `mlflow.genai.evaluate`, §12 Custom Scorers and Feedback, §14 Datasets and Expectations | evaluate over traces, `@scorer` returning `Feedback` with rationale, deterministic checks in scorers and only facts/invented in the judge, expectations logged as trace assessments |
| §28 Common Mistakes #1, #3, #5, #11, #26, #28, #29, #30 | SQL not file store; predict mode OR trace mode, never both; root trace wrapper; expectation key names; context across threads (clients created inside the coroutine); keep traces small; no second tracer; never `mlflow-tracing` next to `mlflow` (we install only `mlflow-skinny`) |
| `AI-Engineering/RAG_CHATBOT_GUIDE.md` §5 (retrieval gates everything), §11 (hybrid + RRF, the D5 trigger target), §21 (Recall@k definition, metric stack) | Recall@5 per source; per-component measurement separate from end-to-end |
| `AI-Engineering/LangChain/LANGGRAPH_GUIDE.md` §21 Observability and Testing (the file is `AI-Engineering/LangChain/LANGGRAPH_GUIDE.md`, found by `find`; Roadmap's "LANGGRAPH_GUIDE" resolves here) | Node-level tracing of the compiled graph via the callback autolog |
| `Foundations/DESIGN_PATTERNS_GUIDE.md` §9 Hexagonal (Ports & Adapters), §14 Retry with Backoff (reasoning only: no retry loops here), §24 Timeout, §29 Agentic AI & LLM Application Patterns | Eval depends on the existing ports; the only adapter that touches MLflow is one module; explicit timeouts on judge and MLflow calls; no hidden retries (rate-limit stop-and-resume instead) |

**Documented exceptions (the plan must list these):**
1. MLFLOW §14 recommends a managed `EvaluationDataset` over "a JSON file in git": **not used**, because D-02 requires public/private split files and D-05 gates on review status; `mlflow.genai.create_dataset` would also need the SQL server to hold handbook-derived records.
2. MLFLOW §11/§13 built-in LLM judges and judge alignment: **not used** (D-08, D-11); judge goes through `LlmClient`.
3. MLFLOW §19-§22 production tracing/monitoring: **out of scope** (D-18, deferred).
4. MLFLOW §24 retention/archival and auth: **not configured** (single user, loopback-only, local volume).
5. RAG §21 RAGAS/DeepEval/TruLens: **not used**; Recall@5 is a few lines of set arithmetic, faithfulness is the D-10 judge.

## Recall@5 definition (question 5)

RAG guide §21 [VERIFIED: Read, lines 1187-1190]: "**Recall@k** - of all the chunks that *should* have been retrieved, how many appeared in the top k?". D-15 locks the hit rule ("any `expected_sources` entry in the top 5"). Report:
- **Primary (gating the D5 flag):** item-level hit rate = fraction of items with at least one expected source in the top 5 (`hit@5`). Compute per source: handbook (handbook items) and Guides (Guides items) separately; flag `guides < 0.8`.
- **Secondary (informational):** mean fractional recall = mean over items of |expected ∩ top5| / |expected|. It equals the primary when each item has one expected source; it differs only for multi-source items.
- Retrieve with `limit=5` explicitly (the bot's own connector defaults are `handbook_limit=3`, `guides_limit=4`, mcp_client.py:159-160; tool max is 10, `MAX_LIMIT: Final = 10`, models.py:22). The query is `" ".join(reformulation.keywords_it)` for handbook and `keywords_en` for Guides, exactly as `retrieve` builds it (workflow.py:128-129).
- Handbook search returns whole pages (22 pages in the current index), so handbook Recall@5 over a 22-page corpus is easy; the number that carries information is Guides.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The MLflow UI deep link for a trace is `{public_url}/#/experiments/{experiment_id}/traces?selectedEvaluationId={trace_id}` (the query parameter `selectedEvaluationId` exists in the shipped UI bundle; the route shape is not verified) | Report format | Broken links in the report; fall back to printing experiment URL + trace id + tag `item_id` (searchable in the UI) |
| A2 | `claude-opus-5-5` (D-08) is accepted by Meridian and maps to an Opus tier available on the owner's Max plan, and the `[1m]` default does not require Extra Usage for small prompts | Pitfall 11 | Every judge call fails or bills Extra Usage. Mitigation: `preflight` command calls each configured model once before any run; set `MERIDIAN_OPUS_MODEL=opus` on the compose `meridian` service for the eval profile |
| A3 | About 300 first-run calls (about 40 items x 3-4 bot calls, <= 40 Opus judge calls, about 28 x 2-3 empty-context calls) fit one Max usage window; reruns are free via cache | Budget | A run stalls mid-way; resumable by design (cache + abort-after-N-errors) but wall-clock grows |
| A4 | `mlflow.genai.evaluate(data=traces)` with scorers does not itself create judge-call traces when `mlflow.anthropic.autolog()` is disabled in the score phase | Pitfall 4 | Cosmetic stray traces; verify in the smoke test by asserting trace count == item count |
| A5 | `docker compose run --rm eval gate` returns the container's exit code, so a non-zero FAIL exit propagates to the shell | Gate | Gate cannot be scripted; verify in `scripts/eval-smoke.sh` |
| A6 | Running the official MLflow image as root with `cap_drop: [ALL]` is acceptable under the user's "Python 3.12 only" and hardening conventions (the image itself uses Python 3.11 and root) | Compose | If rejected, build a project `mlflow_server` Dockerfile stage + hashed lock (Open Question 2) |
| A7 | File-store tracking (`file:` URI) is not needed or usable in unit tests (skinny has no SQLAlchemy); unit tests mock the tracing module | Validation | If a hermetic MLflow store is wanted in unit tests, full `mlflow` (or the compose smoke) is required |
| A8 | The recommended collect-then-evaluate-over-traces split is acceptable as the implementation of D-20 (verdicts attach to each trace, run metrics logged) although D-20 literally says `predict_fn` wrapping `run_workflow` | Summary, Pattern 2 | If the owner requires literal D-20, per-item cache cannot apply to bot runs (reruns cost ~160 bot calls) or traces go hollow on cache hits |
| A9 | The `getpwuid(): uid not found` warnings MLflow logs when the container uid has no passwd entry are harmless (observed with uid 1000; images here use 10001) | Environment | Log noise only; setting `USER=eval` env may silence it (unverified) |

## Open Questions

1. **Does Meridian accept `claude-opus-5-5`, and under what tier/limits?**
   - Known: Meridian docs describe tier aliases and pinned ids (`MERIDIAN_DEFAULT_OPUS_MODEL`), Opus defaults to `[1m]`, `MERIDIAN_OPUS_MODEL=opus` opts out; no Max limits are documented; the repo's `.env` (not read) holds `MERIDIAN_API_KEY`.
   - Unclear: the mapping of the literal id and whether Max quota covers ~40 Opus judge calls plus 160-300 Sonnet/Haiku calls in one window.
   - Recommendation: first task of the live wave is a `preflight` command (one tiny structured call per configured model, prints model id and success) behind a `checkpoint:human-verify`; ship `MERIDIAN_OPUS_MODEL: opus` in the eval profile's meridian service; cap calls and keep the stop-and-resume behaviour.
2. **Root-in-container for the MLflow server acceptable?**
   - Known: official image has no `USER`; a fresh named volume is root-owned; non-root fails.
   - Recommendation: accept root + `cap_drop: ALL` + `no-new-privileges` + loopback-only port (verified working). Switch to a project-built stage only if the owner rejects it.
3. **Minimal bot edits.** `build_llm_client(settings: BotSettings)` needs a `BotSettings` instance (llm.py:118), which requires `allowed_users`, `thread_key_secret`, `mcp_url`, `intake`, `video_thumbnail_url` (config.py:48-77). Recommendation: change only its parameter type to a small structural `Protocol` (`llm_backend`, `anthropic_api_key`, `meridian_api_key`, `llm_base_url`, `llm_timeout_seconds`) so `EvalSettings` reuses the real `LLM_BACKEND` logic; this edit triggers the chat-bot workflow (Pitfall 12) but changes no behaviour. The alternative (duplicate the 20 lines in eval) risks drifting from the bot's backend rules.
4. **Where do `handbook://` expectations of rule-exists sensitive items live?** D-02 says committed no-answer/sensitive items must not quote handbook text, but a rule-exists item's `expected_sources` contains a real `handbook://<page_id>`. Recommendation: any item whose `expected_sources` contains `handbook://` lives in the private file regardless of `kind`; a unit test asserts the committed YAML contains no `handbook://` and no `clickup` string. The owner should confirm that page ids count as private.
5. **Re-score policy for MLflow assessments** (Pitfall 5): decide between "evaluate only unscored traces" and `log_feedback` once per trace/scorer. Recommendation: the former, with `scored` markers in the cache.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker engine | everything | yes | 29.9.1 | - |
| Docker Compose | eval profile | yes | v5.6.0 | - |
| Network to PyPI / GHCR | locks, image pull | yes (executed) | - | - |
| `ghcr.io/mlflow/mlflow:v3.18.0` | EVAL-05 | pulled locally (1.34 GB) | 3.18.0 | project-built stage (Open Q 2) |
| `meridian-claude` external volume | live LLM runs | yes (`docker volume ls`) | - | stub LLM for hermetic smoke only |
| `MERIDIAN_API_KEY` in `.env` | live LLM runs | not checked (secret-guard blocked reading `.env`; do not read it) | - | ask the owner at the live checkpoint |
| Guides checkout | D-01, goldens | yes `~/Desktop/WORK/Guides` @ `4526500`, `GUIDES_INDEX.md` stale | - | - |
| Handbook snapshot | handbook goldens | yes `docs/research/handbook-raw` (23 files; 22 indexed) | - | - |
| Firestore emulator | gap log | in default compose (`google/cloud-sdk:592.0.0-emulators`) | 592.0.0 | `reply.gap_reported` still works if the emulator count check is skipped |
| Host Python | n/a | not used (Docker only) | - | - |

**Missing dependencies with no fallback:** none found. **Live-run prerequisite:** the Max session must be seeded in `meridian-claude` and valid (refresh the login per `services/chat_bot/README.md` if expired).

## Validation Architecture

> `workflow.nyquist_validation` is absent from `.planning/config.json` (only `workflow._auto_chain_active` present), so the section is enabled. [VERIFIED: Read of config.json via cat]

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.2.0 (+ pytest-cov 7.1.0, anyio markers), ruff 0.17.3, mypy 2.4.1 strict [VERIFIED: requirements-dev.txt] |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.run]`, `[tool.mypy]`, `[tool.ruff]`) |
| Quick run command | `./run-unit-tests.sh --single-file test_<module>.py tests/unit/buddy_eval` |
| Full suite command | `./run-unit-tests.sh --all` (ruff check, ruff format --check, mypy, pytest `--cov-fail-under=80`) |
| Network | unit suite runs `--network none`; integration/smoke use compose |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EVAL-01 | golden schema: kinds, review enum, no extra fields; loader merges public+private; missing private file warns and marks set incomplete; committed YAML has no `handbook://`/`clickup`; counts within 30-50 on merged set (committed-only counts asserted when private file absent); lint rejects unknown expected sources against a synthetic index | unit | `./run-unit-tests.sh --single-file test_golden.py tests/unit/buddy_eval` | no, Wave 0 |
| EVAL-01 | The owner reviews drafts (`draft` -> `approved`) | manual checkpoint | `human-verify` plan task | n/a |
| EVAL-02 | recall math (hit-any, fractional, per source), threshold flag at `< 0.8` (0.79 vs 0.80), failed tool call is an error not a miss, reformulation cache hit makes zero LLM calls on second run, source-id resolution of permalinks | unit | `--single-file test_recall.py tests/unit/buddy_eval` | no, Wave 0 |
| EVAL-03 | per-kind scoring table (all rows of Pattern 4 incl. `error`/`smalltalk`), invented count only over answered items, judge prompt contains full source text and fact list and is data-fenced, cache key changes with each key ingredient, errored never cached, resume after interruption | unit (FakeLlm + in-process FastMCP) | `--single-file test_scoring.py` / `test_judge.py` / `test_cache.py` / `test_runner.py` | no, Wave 0 |
| EVAL-03 | live scoring through Meridian | manual/live checkpoint | `docker compose --profile eval run --rm eval run` | n/a |
| EVAL-04 | empty-context PASS when every reply is refusal/referral with `gap_reported`; FAIL when any reply is an answer; fixture index builds, loads in `load_snapshot`, and returns no hits for scripted keywords | unit (scripted FakeLlm; negative case with answering FakeLlm) | `--single-file test_empty_context.py tests/unit/buddy_eval` | no, Wave 0 |
| EVAL-04 | real-LLM empty-context | live checkpoint | `docker compose --profile eval run --rm eval empty-context` | n/a |
| EVAL-05 | compose structure: `mlflow` pinned by digest, `127.0.0.1:5000:5000` is the only published port in the file, `--allowed-hosts` present, telemetry disabled, named volume, in profile `eval`, default services still exactly the seven hermetic ones, `meridian` in `[live, eval]`, eval service has no secret literals | unit (structural, like `test_compose.py`) | `--single-file test_compose.py tests/unit` | exists, must be updated |
| EVAL-05 | each judged item has one trace with spans `reformulate`, `retrieve`, `answer`, `gate`; trace count equals item count; assessments present | smoke (compose + stub LLM + MLflow), asserts through the MLflow REST/search API | `scripts/eval-smoke.sh` | no, Wave 0 |
| EVAL-06 | gate table: 89.9% vs 90.0%, invented 0 vs 1, empty-context fail, any `draft`, missing private file, `errored` items, each failing metric named in output, exit code 0 only on PASS, never PASS on partial runs | unit (pure function + CLI `main([...])` with fakes) | `--single-file test_gate.py tests/unit/buddy_eval` | no, Wave 0 |
| EVAL-06 | real gate | live checkpoint | `docker compose --profile eval run --rm eval gate` | n/a |

### Sampling Rate
- **Per task commit:** `./run-unit-tests.sh --single-file <the touched test file> tests/unit/buddy_eval`
- **Per wave merge:** `./run-unit-tests.sh --all` (also runs the structural tests that this phase edits: compose, dockerfile stages, requirements locks, repo layout, workflows)
- **Before the phase gate:** `scripts/eval-smoke.sh` (hermetic, stub LLM, real MLflow container) then the three live checkpoints (`preflight`, `run`, `empty-context`/`gate`) with the owner present
- **Phase gate:** full suite green and the live `gate` command executed once by the owner before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/buddy_eval/` with `conftest.py` (fixture index via `tests.unit.mcp_server.conftest.write_index/make_content`, `FakeLlm`, `RecordingConnector`, fake tracing sink)
- [ ] `jobs/eval/` skeleton, `jobs/eval/requirements.txt` + `requirements.lock`, Dockerfile `eval` stage, `scripts/lock-requirements.sh` extension (regenerates every lock; note the `cachetools` move)
- [ ] `pyproject.toml`: add `jobs/eval` to `pytest.pythonpath`, `[tool.coverage.run].source` (`buddy_eval`), mypy `mypy_path` and `files` (`jobs/eval/buddy_eval`), ruff `src` and isort `known-first-party`; Dockerfile `base` stage `PYTHONPATH` gains `/app/jobs/eval`
- [ ] Update existing structural tests that hard-code the current shape: `tests/unit/test_compose.py` (`HERMETIC_SERVICES` stays seven; `LIVE_SERVICES`/profiles assertion `["live"]` for meridian; the no-published-port test must allow only mlflow's loopback binding; new eval-profile assertions), `tests/unit/test_dockerfile_stages.py` (`_stage_names() == ["base","test","mcp_server","chat_bot","sync"]`, `PINNED_FROM` stage alternation, `RUNTIME_STAGES`), `tests/unit/test_requirements_lock.py` (`ALL_LOCKS`, `STAGE_LOCKS`, `DEV_INPUTS`), `tests/unit/test_repo_layout.py` (`D11_PATHS`, `PIN_FILES`-style lists), `tests/unit/test_workflows.py` (dependabot set must gain `("pip", "/jobs/eval")` or the entry is omitted; `.github/workflows/tests.yml` paths should gain `jobs/eval/**`), `.github/dependabot.yml`
- [ ] `deploy/compose/stub_llm.py` + `tests/unit/test_stub_llm.py`: add a branch for the judge schema title (the stub currently returns HTTP 400 `unknown schema` for anything but Reformulation/RetryPlan/ContactExtraction/AnswerDraft)
- [ ] `.gitignore`: nothing new needed (`docs/internal/` and `.cache/` already ignored) but add a test that `docs/internal/` stays ignored (exists as `GITIGNORE_REQUIRED` in test_repo_layout)

## Security Domain

> `security_enforcement` is absent from config (treated as enabled).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (single local user; MLflow bound to loopback, no basic-auth) | loopback publish `127.0.0.1:5000`; revisit before any shared host |
| V3 Session Management | no | - |
| V4 Access Control | partial | compose network is private; MLflow not reachable from outside the host; private data only on bind mount under `docs/internal/` |
| V5 Input Validation | yes | `yaml.safe_load` + pydantic `extra="forbid"` for golden files; judge output validated by pydantic (`LlmClient.structured`); reply fields treated as data |
| V6 Cryptography | no | none implemented; no secrets generated |
| V7 Error handling and logging | yes | log counts/ids only, never question or evidence text (repo posture, BOT-11); judge rationale goes to the MLflow trace and report, not to container logs |
| V8 Data protection | yes | handbook text lands in: MLflow SQLite volume, eval cache, JSON reports. All stay local (named volume, `docs/internal/`); never committed; MLflow telemetry disabled (`MLFLOW_DISABLE_TELEMETRY=true`, default is **on**) |
| V14 Configuration | yes | image pinned by digest; `cap_drop: ALL`; `no-new-privileges`; secrets only by `${...}` interpolation (existing test enforces suffix rule); eval container must not get `THREAD_KEY_SECRET` or MCP server env |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Handbook text committed to the public repo (golden file, report, cache) | Information disclosure | D-02 split; unit test: committed YAML has no `handbook://`/`clickup`; reports/cache only under ignored `docs/internal/`; no handbook text in RESEARCH/PLAN files |
| MLflow telemetry exfiltrating usage from a private setup | Information disclosure | `MLFLOW_DISABLE_TELEMETRY=true` on server and client (verified env var name, telemetry/utils.py:154) |
| MLflow UI exposed on the LAN | Information disclosure | publish only `127.0.0.1:5000`; `--allowed-hosts` is an allow-list, never `*` |
| Prompt injection through retrieved text or a model answer reaching the judge | Tampering | Judge prompt fences answer and sources as data (like `format_evidence`), structured output only, no tool access for the judge |
| `LANGSMITH_TRACING` / third-party tracing enabled by accident in the eval image | Information disclosure | Keep `ENV LANGSMITH_TRACING=false` in the eval stage; eval `EvalSettings` refuses it like `BotSettings` does (config.py:20,162-165) |
| Root container (MLflow image) | Elevation of privilege | `cap_drop: ALL`, `no-new-privileges`, no host mounts, loopback port; eval image itself runs uid 10001 or the host user, never root |
| Meridian credentials leaking into eval logs/traces | Information disclosure | `MERIDIAN_API_KEY` only via interpolation; MLflow Anthropic autolog records request payloads: confirm headers/keys are not in spans (autolog logs messages, not the client api key; verify in smoke by grepping trace JSON for the key's presence flag only, never printing it) |

## Sources

### Primary (HIGH confidence)
- Executed experiments in Docker (scratchpad venvs `/work/venv` full mlflow 3.18.0 and `/work/venv2` mlflow-skinny 3.18.0 + pandas, official `ghcr.io/mlflow/mlflow:v3.18.0`, repo `deploy/compose/stub_llm.py` as the LLM): LangGraph node spans, anthropic autolog, async `predict_fn`, evaluate over traces, duplicate feedback, async-trace-logging failure, Host-header 403, non-root volume failure
- MLflow 3.18.0 installed source (`mlflow/genai/evaluation/base.py`, `harness.py`, `genai/utils/trace_utils.py`, `genai/scorers/base.py`, `environment_variables.py`, `telemetry/utils.py`) and `mlflow server --help` output
- PyPI JSON for `mlflow`, `mlflow-skinny`, `mlflow-tracing`, `pandas`; `docker buildx imagetools inspect ghcr.io/mlflow/mlflow:v3.18.0`; `raw.githubusercontent.com/mlflow/mlflow/v3.18.0/mlflow/ml-package-versions.yml`; `raw.githubusercontent.com/mlflow/mlflow/v3.18.0/docker/Dockerfile`
- Repository files read this session: `services/chat_bot/buddy_bot/{workflow,ports,schemas,gate,mcp_client,llm,config,prompts,referral}.py`, `services/mcp_server/buddy_mcp/{models,guides_tools,handbook_tools,gap_tool,gaplog,config}.py`, `packages/buddy_core/buddy_core/{store,index_reader,index_writer,models,escalation}.py`, `jobs/sync/buddy_sync/{guides_index,guides}.py` and `cli.py` (subcommands), `docker-compose.yml`, `Dockerfile`, `run-unit-tests.sh`, `scripts/{sync-and-publish,lock-requirements}.sh`, `pyproject.toml`, requirement files and locks, `deploy/compose/stub_llm.py`, `tests/unit/test_compose.py` (header), test names of dockerfile/lock/layout/workflow tests
- Guides @ `4526500`: `MLFLOW_GENAI_GUIDE.md` §12, §14, §24, §28; `RAG_CHATBOT_GUIDE.md` §21; `GUIDES_INDEX.md` headings for LangGraph and Design Patterns guides

### Secondary (MEDIUM confidence)
- Meridian `docs/configuration.md` @ `cafdcf780f1b40c8f0dee17481132f47b4cbb353` (first 100 000 of 148 997 chars; model-mapping and Max-limit details absent from what was read)
- Meridian README @ the same commit (no model/limit specifics)

### Tertiary (LOW confidence)
- None used as a basis for recommendations; unverified items are in the Assumptions Log (A1-A9)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH for versions and compatibility (executed on pinned stack); MEDIUM for the SUS-flagged pins pending human verification
- Architecture: HIGH (collect/evaluate-over-traces executed end to end; pure/adapter split follows existing repo patterns)
- Pitfalls: HIGH for the 9 executed ones (1-6 and the gate/error-path ones read from source); MEDIUM for Meridian-specific ones (not probeable)

**Research date:** 2026-11-21
**Valid until:** 2026-12-05 for MLflow specifics (3.x releases roughly every 2-3 weeks; a bump needs the smoke re-run), 2026-12-21 for repo-structure findings
