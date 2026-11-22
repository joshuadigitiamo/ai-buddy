# buddy_eval: evaluation job and Milestone 1 gate

Batch job, run on demand from the developer laptop, that answers one question: does Milestone 1 pass? It runs the real bot workflow (the same `run_workflow` the chat bot uses, over a real MCP connection) on every approved item of the golden set, judges the answers, runs the empty-context test, and prints one line, `GATE: PASS` or `GATE: FAIL`, followed by one `FAIL <metric>: <detail>` line for each failing metric. It exits 0 only on `PASS`.

It is never deployed and no CI job runs it. Everything runs in Docker; do not run it with the host Python.

## The gate rule (D-17)

`GATE: PASS` needs all of these. Anything missing, skipped, errored, unjudged or still a draft makes it `FAIL` with the metric named.

| Metric (fixed print order) | PASS needs |
|----------------------------|------------|
| `golden_set` | the private handbook file present, no `draft` item, at least one approved item, and a golden set that loads |
| `errored` | no approved item errored (a model, MCP or judge failure) and the run was not stopped early |
| `correctness_with_citation` | at least 90% of approved items correct with a matching citation (exact fraction, so 9 of 10 passes and 8 of 9 does not), none left unjudged |
| `invented_policies` | zero answers flagged by the judge with an unsupported claim; a run too incomplete to count them is `not measured` and fails |
| `empty_context` | every approved handbook and Guides item is refused, with a logged gap, over the unrelated fixture index |

Recall@5 of the two search tools is printed first as `recall (informational, not gating):`. It informs the hybrid-retrieval decision (D5) and never changes the verdict. Recall errors are printed as `recall: INCOMPLETE (...)` and are ignored by the gate.

A partial invented-policy count that already holds a flagged item is printed as counted (`invented_policies: 2 > 0`); a partial count of zero is `not measured`.

## Commands

The job image is built from the `eval` target. Run every command through compose, from the repository root:

```bash
docker compose --profile eval run --rm eval <command>
```

The eval profile starts the MCP server, a second MCP server over the empty-context fixture index (`mcp-server-empty`, built by the one-shot `eval-fixture`), the local MLflow server and Meridian. The shell needs the variables compose reads (see `docker-compose.yml`): `HANDBOOK_SRC_DIR`, `GUIDES_SRC_DIR`, `REDACT_PAGE_FILES`, a `THREAD_KEY_SECRET` of at least 32 characters, and `HOST_UID` and `HOST_GID` so the job can write into the private directory. Run the `sync` service once first so the artifacts volume holds an index.

| Command | What it does | Exit code |
|---------|--------------|-----------|
| `python -m buddy_eval gate` | The one command: recall (informational), the scoring run, the empty-context test, then the verdict. Reuses every cache. | 0 only on `GATE: PASS`, 1 on `GATE: FAIL` or an error, 2 on bad arguments |
| `preflight` | One tiny structured call per configured model (reformulate, answer, judge), one MCP session, and a connection to the MLflow server. Prints `preflight <check> <target>: ok` or `failed (<ErrorType>)`. Run it before the first live run. | 0 only when all five checks pass |
| `lint` | Checks the golden set against the schema, the index and the privacy rules. No model, MCP or MLflow use. | 0 unless an error is found |
| `recall [--item ID]` | Recall@5 of handbook and Guides search with the bot's own reformulation. | 1 if an item errored |
| `run [--item ID]` | Runs approved items through the bot, judges them and scores the traces. | 1 if an item errored or the run stopped early |
| `empty-context [--item ID]` | Every approved handbook and Guides item must be refused with a logged gap over the fixture index. | 0 only when every item is refused |
| `build-fixture --dest DIR` | Builds the fixture index from its committed sources. Needs no settings. | 0 on success |

The container entrypoint is `python -m buddy_eval`, so `docker compose --profile eval run --rm eval gate` runs `python -m buddy_eval gate`.

### What `gate` prints

Console lines carry item ids, kinds, statuses, numbers and trace links only. Question, answer and evidence text never reach the console or a log (see Privacy).

- When the golden set is not ready (private file missing, any draft, no approved item, or a load error) the gate prints `GATE: FAIL`, the `FAIL golden_set: ...` lines and `SKIPPED recall, run, empty_context: golden set not ready (no model call made)`. It makes no model, MCP or MLflow call, so a golden set that cannot pass spends no Max quota.
- When the scoring run stops after consecutive errors, the gate prints `SKIPPED empty_context: run stopped after consecutive errors` and fails with `errored` and `empty_context: not run`.
- The gate writes `gate-<UTC>.json` under `PRIVATE_DIR/eval/reports` with the metrics, the verdict, the failing item ids and the index identity. The scoring run writes its own `run-<UTC>.json` with the judge reasoning. Both stay under the private directory.

## Settings

Every setting comes from the environment (`EvalSettings`); no env file is read by the job. Compose passes them from `EVAL_*` host variables where noted. Errors name variables, never values.

| Variable | Meaning |
|----------|---------|
| `LLM_BACKEND` | `meridian` (default) or `api`. `vertex` is not enabled. Compose: `EVAL_LLM_BACKEND`. |
| `LLM_BASE_URL` | Meridian or stub URL. Compose: `EVAL_LLM_BASE_URL`. |
| `MERIDIAN_API_KEY`, `ANTHROPIC_API_KEY` | Keys; the `api` backend needs the Anthropic one. Never printed. |
| `LLM_TIMEOUT_SECONDS` | Bound of every model call, preflight included. Default 60. |
| `REFORMULATE_MODEL`, `ANSWER_MODEL`, `JUDGE_MODEL` | Model ids. The judge must differ from the answer model (D-08). |
| `CONFIDENCE_THRESHOLD` | The bot's gate threshold. Default 0.7. |
| `MCP_URL`, `MCP_EMPTY_URL` | The real MCP server and the fixture one. |
| `GOLDEN_PUBLIC_PATH`, `GOLDEN_PRIVATE_PATH` | The two golden files. Compose: `EVAL_GOLDEN_PUBLIC_PATH`, `EVAL_GOLDEN_PRIVATE_PATH`. |
| `PRIVATE_DIR` | Where the cache and the reports are written. Compose mounts `EVAL_PRIVATE_DIR` (default `./docs/internal`) at `/private`. |
| `ARTIFACT_DIR`, `FIXTURE_DIR` | The real index and the empty-context fixture index, read-only. |
| `EMPTY_GAP_COLLECTION`, `FIRESTORE_EMULATOR_HOST`, `GOOGLE_CLOUD_PROJECT` | The gap collection of the empty-context server and the emulator used to cross-check it. |
| `MLFLOW_TRACKING_URI`, `MLFLOW_EXPERIMENT`, `MLFLOW_UI_BASE_URL` | The local MLflow server; the URI must be `mlflow`, `localhost` or `127.0.0.1`. |
| `MAX_CONSECUTIVE_ERRORS`, `ITEM_PAUSE_SECONDS` | Stop-and-resume limit (default 3) and the pause between items (default 0.5 s). |

`LANGSMITH_TRACING` and `LANGCHAIN_TRACING_V2` must stay false: prompts must not leave the host.

## Private paths and cache reset

| Path (default, on the host) | Content |
|------------------------------|---------|
| `docs/internal/golden-handbook.yaml` | The handbook items of the golden set. Gitignored; the repository is public. |
| `docs/internal/eval/cache/` | Collected outcomes, judge verdicts, reformulations and empty-context outcomes, keyed by item, index identity, bot version and models. |
| `docs/internal/eval/reports/` | `gate-*.json`, `run-*.json`, `recall-*.json`, `empty-context-*.json`. Report file names carry the UTC second, so two runs of the same command in the same second overwrite each other. |

Deleting `docs/internal/eval/cache/` forces a fresh run with new model calls. A change of the index, the bot version, a model or an item changes the cache key by itself, so you rarely need to.

## Golden set

Two files are merged by id (D-02): the committed Guides file `jobs/eval/golden/guides.yaml` (Guides, no-answer and sensitive-without-rule items) and the private handbook file above. A committed item must never cite a handbook page.

Each item has: `id` (lowercase letters, digits, `-` and `_`, 3 to 64 characters, for example `gd-01`), `kind` (`handbook`, `guides`, `no_answer`, `sensitive`), `question`, `expected_answer`, `key_facts`, `expected_sources`, `expected_referente_role`, `review` and `review_note`. A handbook item cites the handbook scheme only; a Guides item cites `file#section` prefixes present in the index; a `no_answer` item has neither facts nor sources and names the role it should refer to.

Review flow: Claude drafts items with `review: draft`; Joshua reads each one and sets `approved` or `rejected` (D-07). Only `approved` items are run. Any `draft` makes the gate fail. Run `lint` after every edit.

After editing `jobs/eval/golden/guides.yaml`, rebuild the eval image, because the file is copied into it:

```bash
docker compose --profile eval build eval
```

## MLflow UI

The traces are inspectable at `http://127.0.0.1:5000` (loopback only; the only published port of the stack). Each item is one `bot_run` trace with the workflow node spans, the model calls, its expectations and the verdict feedback; the gate output prints a link per item. The MLflow volume holds questions and handbook text, so it stays on the host and is never pushed anywhere (D-21).

## Max budget behaviour

The judge and the bot use Joshua's Max session through Meridian, so calls are spent with care:

- Items run one at a time, in id order, with `ITEM_PAUSE_SECONDS` between fresh items (the MCP server rate limit counts every request).
- After `MAX_CONSECUTIVE_ERRORS` errors in a row the run stops and prints `stopped after N consecutive errors; re-run the same command to resume`. An errored item is never cached, a completed one is, so running the same command again resumes from the cache.
- A second `gate` over unchanged inputs makes no model call.
- The gate checks the golden set first and spends nothing when it cannot pass.
- Run `preflight` before the first live run. A successful `judge` ping is the evidence that the Opus judge model works within the plan; Meridian's tier mapping is not visible to the client.

## Privacy

The console and the logs carry ids, numbers, model ids, host names, error type names and trace links. The judge reasoning, the invented claims and the answers go to the JSON reports under the private directory and to the local traces. Preflight prints no key, no URL credentials and no prompt text.

## Decision amendment: D-20

D-20 asked for `mlflow.genai.evaluate` with a `predict_fn` wrapping the workflow. A cached `predict_fn` result produces a hollow trace on every rerun, so the job collects each item under its own `bot_run` root trace first and then scores the collected traces in trace mode. Verdicts still attach to each trace, so every judged answer is inspectable in the UI with its retrieval, generation and gate spans.

## Guides applied

- `AI-Engineering/MLFLOW_GENAI_GUIDE.md`: section 10 "Evaluation Basics" and section 24 "Self-Hosting". The gate reads its numbers from local verdicts; the MLflow server holds the inspectable traces.
- `AI-Engineering/RAG_CHATBOT_GUIDE.md`: section 21 "Evaluation, Retrieval and Generation Metrics" and section 11 "Hybrid Retrieval and RRF". Retrieval and end-to-end metrics are reported side by side; Recall@5 informs D5 without gating.
- `Foundations/DESIGN_PATTERNS_GUIDE.md`: section 24 "Timeout" and section 29 "Agentic AI and LLM Application Patterns". Preflight bounds each model call by `LLM_TIMEOUT_SECONDS`; the gate is a pure decision over measured inputs.

## Smoke test

`scripts/eval-smoke.sh` runs the hermetic stack (stub LLM, real MLflow container, no Meridian, no Max session): it checks that every item produced exactly one trace, then runs `eval gate` and checks that the container exit code is 0 exactly when the printed line is `GATE: PASS`.
