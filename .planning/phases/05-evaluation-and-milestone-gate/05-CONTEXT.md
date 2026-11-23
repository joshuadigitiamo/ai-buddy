# Phase 5: Evaluation and Milestone Gate - Context

**Gathered:** 2026-11-21
**Status:** Ready for planning

<domain>
## Phase Boundary

The developer runs one command and learns whether Milestone 1 passes its gate (correctness-with-citation >= 90%, 0 invented policies, empty-context test passes), with every judged answer inspectable as an MLflow trace. Deliverables: a reviewed golden set (~40 items), a Recall@5 command (handbook + Guides, flags the D5 hybrid trigger), an end-to-end scoring command over the real bot workflow, the empty-context test, a containerized MLflow server, and the gate command (EVAL-01..06).

Not in this phase: hybrid dense+BM25 retrieval (D5; only triggered by the Recall@5 result, its own phase), tracing the live/deployed bot, CI running the LLM eval, the HR-sourced golden set, open-model A/B (D9), any multi-user rollout work.

</domain>

<decisions>
## Implementation Decisions

The owner chose the first four Golden-set answers explicitly, then said "On this phase accept all your recommendations": every remaining decision below is Claude's recommended option, approved by the owner.

### Prerequisite (before drafting the golden set)
- **D-01:** The Guides checkout was fast-forwarded on 2026-11-21 to `4526500` (8 commits; 10 guides edited: RAG_CHATBOT, MCP_SERVERS, MULTI_AGENT_ARCHITECTURE_DESIGN, AIRFLOW, BIGQUERY_DATA_WAREHOUSE, BIG_DATA_FRAMEWORKS, ETL_VS_ELT, CICD, CLOUD_DEPLOYMENT, KUBERNETES; ETL vs ELT video re-cut). `GUIDES_INDEX.md` in the Guides repo was last updated 2026-11-03 and is stale. The first plan regenerates `GUIDES_INDEX.md` (the owner commits it in the Guides repo), re-runs the sync and publish (`sync-and-publish.sh`), and confirms the drift check is green, before any golden item is drafted. Golden expected sources are taken from that fresh index. Recall and scoring runs record the Guides commit and the index content hash.

### Golden set
- **D-02:** Split storage. Guides items are committed (`eval/golden/guides.yaml`, or a path the planner picks). Handbook items live gitignored at `docs/internal/golden-handbook.yaml` (`docs/internal/` is already ignored; `docs/research/` is committed apart from `handbook-raw/`, so not there). The loader merges both files and warns loudly if the handbook file is missing; the gate then FAILs (incomplete set). Committed no-answer and sensitive items must not quote handbook text. — **Reversibility:** costly — committing handbook-derived content to the public repo cannot be undone (git history), so the split must hold from the first commit.
- **D-03:** About 40 items: 15 handbook-answerable, 13 Guides-answerable, 7 no-answer, 5 sensitive-escalation. Sensitive items cover both D-06 branches from Phase 3: a written general rule exists (cited rule + referral) and no rule exists (referral only).
- **D-04:** Item schema (fields; planner finalizes names): `id`, `kind` (`handbook | guides | no_answer | sensitive`), `question` (Italian), `expected_answer` (short reference answer), `key_facts` (list of facts a correct answer must contain), `expected_sources` (list of `source_url`: `handbook://<page_id>` or Guides permalink/section id), `expected_referente_role` (sensitive/no-answer), `review` (`draft | approved | rejected`), `review_note`. No item points at the official handbook doc.
- **D-05:** Review status gates the gate: scoring counts only `approved` items; the gate refuses PASS (prints FAIL "golden set not fully reviewed") while any item is `draft`. `rejected` items are excluded.
- **D-06:** Single-turn items only (empty history). Follow-up behaviour stays covered by Phase 3 tests.
- **D-07:** Claude drafts all items, the owner reviews them (an existing locked decision, see INGEST-CONFLICTS). Drafting is a plan task that ends in a human-review checkpoint.

### Judging
- **D-08:** The LLM judge is Opus 5.5 (`claude-opus-5-5`), a different model from the Sonnet 5.5 answer step, to limit self-preference. It goes through the existing `LlmClient.structured()` and `LLM_BACKEND` (Meridian in M1), and the model id comes from config. MLflow's built-in provider judges are not used: they would need their own provider credentials or base_url wiring around Meridian.
- **D-09:** Correct-with-citation:
  - **Answerable items:** the reply is an answer, it contains every `key_facts` entry with nothing contradicting them (judge verdict), and at least one cited `source_url` is in `expected_sources` (deterministic check).
  - **No-answer items:** correct iff the reply is a refusal and a gap was logged.
  - **Sensitive items:** correct iff the reply is a referral naming the expected role, plus, in the rule-exists branch, a cited general rule from `expected_sources`.
  - The headline % is over all approved items.
- **D-10:** Invented policy. The judge receives the answer plus the full text of every source the answer cites, as the tools returned it in that run. It flags any normative claim (rule, obligation, entitlement, number, deadline, contact) that the cited text does not support. The invented-policy count is the number of answered items with at least one flagged claim. It is counted on every item that produced an answer, refusal items included if they wrongly answered.
- **D-11:** No human override of judge verdicts in M1. The report lists every failed item and every invented-policy flag, with the judge's reasoning and the MLflow trace link, for the owner to inspect. The judge prompt has deterministic unit tests (stub LLM) only.

### Eval runtime and budget
- **D-12:** New eval package under `jobs/eval` (e.g. `buddy_eval`), with its own Dockerfile stage and its own requirements (mlflow pinned and passed through the legitimacy gate, like every new pin). Commands (names are planner's discretion): `recall`, `run`, `empty-context`, `gate`. Everything runs in Docker through a compose `eval` profile.
- **D-13:** Scoring runs `run_workflow` in-process in the eval container against the compose `mcp-server` over real MCP HTTP, with the real local index, the Firestore emulator gap log and the real LLM through `LLM_BACKEND` (the `meridian` compose service). No Chat API, no Cloud Run target.
- **D-14:** Budget control for Max limits (~40 items × ~3-4 bot calls + 1 judge call):
  - Sequential, with low fixed concurrency (1-2).
  - Per-item result cache keyed by golden-item hash + index hash + bot code/prompt version + model ids, so an interrupted or rate-limited run resumes and reruns are free.
  - An `--item` filter for single items.
- **D-15:** Recall@5 runs per answerable item: handbook items go to `handbook_search`, Guides items to `guides_search`. A hit is any `expected_sources` entry in the top 5. The query is the bot's actual Haiku reformulation, since raw Italian against English Guides BM25 would understate recall. The reformulation is cached (same cache as D-14), so after the first run Recall@5 costs no LLM calls. Guides Recall@5 < 0.8 prints the D5 hybrid-upgrade trigger. No-answer and sensitive items are excluded from Recall.
- **D-16:** Empty-context test:
  - Index: a second compose `mcp-server` instance points at a separate artifact volume holding a small committed fixture index of unrelated content. It is not an empty index, so cold-start guards don't fire.
  - Run: every approved answerable golden question goes through the real LLM.
  - Pass rule: PASS iff every reply is a refusal or referral and a gap is logged for each; any answer → FAIL.
  - A deterministic stub-LLM variant also runs in the unit suite.
- **D-17:** The gate runs recall (informational, not gating), scoring and empty-context, reusing the per-item cache. It prints PASS only when correctness-with-citation >= 90%, invented = 0, empty-context passes and no item is `draft`. Otherwise it prints FAIL naming each failing metric. Non-zero exit on FAIL.

### MLflow
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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scope and requirements
- `.planning/ROADMAP.md` §Phase 5: goal and 5 success criteria
- `.planning/REQUIREMENTS.md`: EVAL-01..06
- `.planning/PROJECT.md`: Milestone 1 gate, D1a (Meridian single user), D4/D5 (retrieval, Recall@5 < 0.8 hybrid trigger), D9, D16 (Guides best practices applied per phase)
- `.planning/INGEST-CONFLICTS.md`: golden set drafted by Claude from the handbook snapshot + Guides, reviewed by the owner

### Prior phase decisions that constrain eval
- `.planning/phases/03-google-chat-bot/03-CONTEXT.md`: D-01..D-07 (gate signals, citation by `source_url`, retry-once, refusal + referente, sensitive detection and handling), D-17 (Haiku reformulate / Sonnet answer)
- `.planning/phases/04-infrastructure-and-ci-cd/04-CONTEXT.md`: D-06..D-10 (laptop sync + publish, artifact stores), D-18 (video offsets)

### Guides best practices (D16) — `~/Desktop/WORK/Guides`, commit 4526500
- `AI-Engineering/MLFLOW_GENAI_GUIDE.md` §3 (server setup), §5-6 (tracing, autolog), §10 (`mlflow.genai.evaluate`), §12-13 (custom scorers and judges, judge alignment), §14 (eval datasets/expectations), §24 (self-hosting, retention, PII), §28 (common mistakes)
- `AI-Engineering/RAG_CHATBOT_GUIDE.md` §5 (retrieval quality gates everything), §11 (hybrid + RRF, the D5 trigger target), §21 (retrieval and generation metrics)
- `DESIGN_PATTERNS_GUIDE` and LangGraph guidance: locate the file in the Guides repo (no `*/LANGGRAPH_GUIDE.md` found at this path; the planner finds the current name)

### Sources
- `docs/research/handbook-raw/` (gitignored, via `HANDBOOK_DIR`): the handbook snapshot, the source of handbook golden items
- `~/Desktop/WORK/Guides` + `GUIDES_INDEX.md`: the source of Guides golden items (regenerate first, D-01)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `services/chat_bot/buddy_bot/workflow.py`: `run_workflow(question, history, deps) -> BotReply` is the eval's predict entry. `WorkflowDeps(llm, mcp, config)` is injectable. Graph nodes: reformulate, smalltalk, retrieve, retry_plan, answer, gate, finish, refuse. Gaps are logged in `_log_gap` for refusal/referral.
- `services/chat_bot/buddy_bot/ports.py`: the `LlmClient.structured()` protocol (reused by the judge), plus `McpConnector` / `McpTools` (handbook_search, guides_search, report_gap)
- `services/chat_bot/buddy_bot/llm.py`: `build_llm_client` and `AnthropicMessagesClient` (meridian | api backends)
- `services/chat_bot/buddy_bot/schemas.py`: `BotReply`, `Reformulation`, `AnswerDraft` with `grounded`/`confidence`
- `deploy/compose/stub_llm.py`: the stub LLM, for deterministic eval unit tests and the stub empty-context variant
- `docker-compose.yml`: services firestore, pubsub, sync, mcp-server, stub-llm, chat-bot, meridian, chat-bot-live, plus volumes `artifacts` and `meridian-claude`. Add an `eval` profile here.
- `jobs/sync`: the pattern for a job package with its own Dockerfile stage and requirements

### Established Patterns
- Everything in Docker; `run-unit-tests.sh` modes; pinned requirements with a legitimacy gate for new pins (mlflow is new)
- The public repo keeps handbook content gitignored (`docs/internal/`, `docs/research/handbook-raw/`)
- Ports and adapters with injected deps; fakes and stubs in unit tests

### Integration Points
- The eval container joins the compose network to reach `mcp-server` (HTTP MCP) and `meridian`
- A second `mcp-server` instance on the fixture artifact volume serves the empty-context test
- MLflow tracking URI is passed to the eval container via env

</code_context>

<specifics>
## Specific Ideas

- Gate output must name the failing metric(s), not just FAIL.
- Every FAIL and invented-policy flag in the report carries its MLflow trace link.

</specifics>

<deferred>
## Deferred Ideas

- Human override of judge verdicts (a reviewed-verdict file the gate honours): revisit if judge disagreements show up.
- Tracing the live/deployed bot (production monitoring, MLFLOW_GENAI_GUIDE §19/§21): before any shared rollout.
- Running the LLM eval in CI: needs an API-key `LLM_BACKEND`, not Meridian.
- Hybrid dense+BM25 retrieval: its own phase, triggered only if Guides Recall@5 < 0.8 (D5).
- Multi-turn golden items exercising thread memory.
- HR-sourced golden set replacing the Claude-drafted one (when the official handbook is ready).

</deferred>

---

*Phase: 05-evaluation-and-milestone-gate*
*Context gathered: 2026-11-21*
