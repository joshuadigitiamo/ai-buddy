# API Coverage — Phase 5

> Full coverage by default. Opt-outs are explicit, reasoned decisions.
> Phase 5 integrates one new external surface: MLflow (Python client `mlflow-skinny` 3.18.0 and the self-hosted MLflow server `ghcr.io/mlflow/mlflow:v3.18.0`). It reuses, unchanged, the Anthropic Messages client through Meridian (see 03 COVERAGE.md; the judge uses the same `messages.create` path), the project's own MCP tools over HTTP (see 02 and 03 COVERAGE.md) and the Firestore emulator REST list endpoint (read-only gap count).

## MLflow Python client, mlflow-skinny (plans 05-04, 05-06, 05-07, 05-08, 05-10, 05-12)

| capability | decision | reason |
|---|---|---|
| set_tracking_uri / set_experiment | INTEGRATE | |
| start_run with run name and tags (index identity, bot version, models) | INTEGRATE | |
| LangChain/LangGraph autolog (node spans) | INTEGRATE | |
| Anthropic autolog (LLM-call spans), suspended in judge and score phases | INTEGRATE | |
| mlflow.trace decorator (bot_run root span), update_current_trace tags | INTEGRATE | |
| get_last_active_trace_id / get_trace / search_traces | INTEGRATE | |
| log_expectation (expected sources, key facts, role, kind, expected outcome) | INTEGRATE | |
| genai.evaluate over traces with custom @scorer Feedback | INTEGRATE | |
| mlflow.genai.evaluate with a prediction function | OPT-OUT | explicitly out of scope: amended D-20 (collect-then-score) avoids hollow traces on cached reruns and the extra validation call |
| log_feedback per trace | OPT-OUT | not needed: evaluate over unscored traces attaches feedback; scored markers prevent duplicates |
| built-in scorers and LLM judges, make_judge, judge alignment | OPT-OUT | explicitly out of scope: D-08 (judge through LlmClient and Meridian) and D-11 (no alignment or override in M1) |
| managed evaluation datasets (create_dataset, EvaluationDataset) | OPT-OUT | explicitly out of scope: D-02 split public/private files and D-05 review gating; the server would hold handbook-derived records |
| log_metric / log_param on the run | OPT-OUT | not needed: evaluate logs scorer means; gate numbers come from the local cache, never from MLflow |
| model registry, logged models, model_id linking | OPT-OUT | not needed: no model artifact is trained or versioned |
| prompt registry | OPT-OUT | not needed yet: prompts live in the bot code and their hash is part of the cache key |
| production monitoring, online scoring, assessment-based alerts | OPT-OUT | explicitly out of scope: D-18 and the deferred idea "tracing the live/deployed bot" |
| MLflow AI Gateway, cost tracking (mlflow[genai] extra) | OPT-OUT | not needed: Meridian is the gateway; cost is not tracked in M1 |
| Databricks or any remote tracking URI | OPT-OUT | explicitly out of scope: D-21; EvalSettings refuses a non-local MLFLOW_TRACKING_URI |
| usage telemetry | OPT-OUT | explicitly out of scope: privacy (MLFLOW_DISABLE_TELEMETRY=true on client and server) |

## MLflow server, self-hosted (plans 05-06, 05-12, 05-13)

| capability | decision | reason |
|---|---|---|
| tracking and trace REST API on the compose network (Host allow-list) | INTEGRATE | |
| UI on 127.0.0.1:5000 for trace and feedback inspection | INTEGRATE | |
| SQLite backend store and proxied artifact store on a named volume | INTEGRATE | |
| healthcheck on the experiments search API | INTEGRATE | |
| authentication (basic auth, app plugins) | OPT-OUT | not needed: single local user, loopback-only port; revisit before any shared host |
| retention, archival and garbage collection | OPT-OUT | not needed: local volume, RESEARCH exception 4 (MLFLOW §24) |
| gunicorn or waitress server options | OPT-OUT | not needed: they disable the Host allow-list middleware (MLFLOW §24) |
| remote artifact stores (S3, GCS) | OPT-OUT | explicitly out of scope: D-21 never pushed anywhere; the volume holds handbook text |

## Firestore emulator REST (plan 05-10)

| capability | decision | reason |
|---|---|---|
| list documents of the empty-context gap collection (count only, paginated) | INTEGRATE | |
| read document fields, write, delete | OPT-OUT | not needed: the cross-check counts documents; writes stay with the MCP server's gap tool |
