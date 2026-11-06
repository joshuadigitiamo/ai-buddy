---
phase: 02-mcp-server-and-skill
plan: 03
subsystem: infra
tags: [firestore, emulator, docker-compose, fernet, py-key-value-aio, gaplog, oauth-storage, hexagonal]

requires:
  - phase: 02-mcp-server-and-skill
    provides: "buddy_mcp package, GAP_MARKER, pinned google-cloud-firestore and fastmcp (plan 02-01)"
provides:
  - "GapLog port, GapRecord (validated, bounded), gap_document (six keys, no identity), FirestoreGapLog (lazy client), InMemoryGapLog"
  - "build_oauth_storage: memory store or Fernet-encrypted Firestore store for the OAuth proxy client_storage"
  - "./run-unit-tests.sh --emulator and docker-compose.test.yml: Firestore emulator tests in Docker, offline --all unchanged"
affects: [02-04 buddy_report_gap tool, 02-05 auth, 02-07 composition root, 04 deploy (TTL policy)]

actuals:
  tokens: 4770
  tasks: 3
  commits: 5
plan_head_before: 75c05b15697be487211a5ec20f46005022d0e717
plan_head_after: 44252acd2d71471ecb160b565414a95df6629406

tech-stack:
  added: []
  patterns:
    - "Port + adapters for the gap log (Protocol, Firestore adapter, in-memory double beside it), mirroring ArtifactStore"
    - "Firestore client built lazily on first use by an injected factory"
    - "Emulator tests carry pytest.mark.firestore plus a skipif on FIRESTORE_EMULATOR_HOST; only --emulator sets the host"

key-files:
  created:
    - services/mcp_server/buddy_mcp/gaplog.py
    - services/mcp_server/buddy_mcp/oauth_storage.py
    - docker-compose.test.yml
    - tests/integration/conftest.py
    - tests/integration/test_firestore_gaplog.py
    - tests/integration/test_firestore_oauth_store.py
    - tests/unit/mcp_server/test_gaplog.py
    - tests/unit/mcp_server/test_oauth_storage.py
  modified:
    - run-unit-tests.sh
    - pyproject.toml

key-decisions:
  - "No mypy override for google.cloud.* was needed: google-cloud-firestore ships type information, so the plan's conditional override was not added."
  - "FirestoreStore is built directly (project=...), not behind a lazy wrapper: google-cloud-firestore opens its gRPC channel on first use, so construction binds no event loop. The emulator test builds the store outside the running loop to prove it."
  - "cryptography.fernet.Fernet is imported directly (transitive of fastmcp, already in the image, no new pin) because the wrapper's source_material/salt path derives a key with PBKDF2 and the env var carries a ready Fernet key."
  - "FernetEncryptionWrapper uses raise_on_decryption_error=False, as fastmcp's own default store does: a rotated key makes stored OAuth state read as missing and the client re-registers instead of the server failing."
  - "Firestore key and collection sanitization strategies (V1) are enabled so OAuth keys containing slashes or reserved patterns cannot break document ids."
  - "Requirements not marked complete: this plan provides storage only. MCP-05 needs the buddy_report_gap tool (02-04), MCP-07 needs auth and rate limiting (02-05). MCP-01 already reads Complete."

patterns-established:
  - "Exact-text gap document: gap_document() is the only place a Firestore gap payload is built; tests assert the key set and no key matching user|email|ip|session|client|sub"
  - "RED stubs that keep imports valid so TDD failures are assertion failures, not collection errors"

requirements-completed: []

duration: ~25min
completed: 2026-11-06
status: complete
---

# Phase 2 Plan 3: Gap Log, OAuth State Store and Emulator Tests Summary

**Gap-log port with a Firestore adapter and a Fernet-encrypted Firestore OAuth store, both proven against the real Firestore emulator by one command (`./run-unit-tests.sh --emulator`) while `--all` stays offline.**

## Performance

- **Duration:** about 25 min (start time was not recorded; estimated from the session)
- **Completed:** 2026-11-06
- **Tasks:** 3 (Task 1 tracer, Tasks 2 and 3 TDD)
- **Files modified:** 10 (8 created, 2 modified)

## Accomplishments

- Tracer: a gap record written through `FirestoreGapLog` lands in the emulator with exactly `question, marker, created_at, expire_at, build_id, tried`; `marker` is `nessuna fonte trovata`, `expire_at - created_at` is exactly 90 days, no key matches the identity pattern. `./run-unit-tests.sh --emulator` brings the emulator up with `docker compose up --wait`, runs `pytest -m firestore tests/integration`, and tears it down on EXIT.
- `GapRecord.new` enforces: question stripped, 1 to 2000 code points (2000 accepted, 2001 rejected, accented text counted by characters), timezone-aware `now` (converted to UTC), `ttl_days >= 1`, `tried` capped at 10 entries of at most 200 characters with blanks dropped. Error messages are fixed strings and never carry the question.
- `FirestoreGapLog` creates its client on the first `record` call (factory called once across calls), verified offline with a fake client; `InMemoryGapLog` is ready for the 02-04 tool tests.
- `build_oauth_storage("memory")` returns the py-key-value-aio memory store; `("firestore", ...)` refuses without `OAUTH_STORAGE_ENCRYPTION_KEY` (missing, blank or invalid Fernet key, never echoing the key) or `GOOGLE_CLOUD_PROJECT`, and otherwise returns `FirestoreStore` wrapped in `FernetEncryptionWrapper`. On the emulator a stored value round-trips, the sentinel never appears in any document of any collection, and a different key reads nothing. No file-backed store exists.

## Task Commits

1. **Task 1 (tracer): FirestoreGapLog to the emulator** - `d55ac28` (feat)
2. **Task 2 (TDD): GapRecord rules and InMemoryGapLog** - RED `9ad9b95` (test), GREEN `d91217d` (feat)
3. **Task 3 (TDD): OAuth state store** - RED `3fed91f` (test), GREEN `44252ac` (feat)

No REFACTOR commits (nothing to clean up).

## TDD Gate Compliance

Both TDD tasks have a `test(02-03)` commit followed by a `feat(02-03)` commit.

- **Task 2 RED:** `test_gaplog.py` run against a no-validation stub: 12 failed, 4 passed (`./run-unit-tests.sh --single-file test_gaplog.py tests/unit/mcp_server`). Failures are on the planned assertions: blank and over-length questions did not raise, naive datetime and `ttl_days < 1` did not raise, question not stripped, `tried` not capped or truncated, `InMemoryGapLog` did not append. Semantic assessment: target tests executed and failed for the intended reason; the 4 passing tests cover behavior already delivered by the tracer (document keys, lazy client) or trivially true on the stub (accented length, ttl 1 day).
- **Task 3 RED:** `test_oauth_storage.py` against a memory-only stub: 4 failed (`DID NOT RAISE OAuthStorageError` for missing key, blank key, missing project, invalid key), 1 passed (memory round trip). Emulator run: the encrypted round-trip test failed on `the emulator holds at least the stored document` (the stub never wrote to Firestore); the wrong-key test passed trivially against two separate memory stores. Semantic assessment: valid RED for the validation and ciphertext behaviors; the wrong-key test only gains meaning after GREEN.
- `workflow.tdd_mode` is `false` in config, and the `gsd_run check tdd-red-evidence` classifier has no pytest report adapter (pytest text output is not one of its supported formats), so it was not run. RED evidence above is from the real pytest output.
- Each RED commit includes a minimal stub of the module so the tests fail on assertions instead of an import error (a missing module would have been an invalid RED).

## Verification

- `./run-unit-tests.sh --all`: exit 0. ruff check, ruff format --check and mypy --strict clean. **423 passed, 17 skipped** (14 earlier local-only skips plus the 3 emulator tests: 1 gap-log, 2 OAuth-store), coverage 97.45% (gate 80%). `gaplog.py` 100%, `oauth_storage.py` 87% (the Firestore branch is exercised on the emulator, not offline).
- `./run-unit-tests.sh --emulator`: exit 0, **3 passed, 0 skipped**, 3 warnings (upstream "configured store is unstable" UserWarning from py-key-value-aio). Emulator container is removed afterwards.
- `./run-unit-tests.sh --single-file test_toolchain.py tests/unit`: 4 passed (existing modes unchanged).
- Acceptance greps: `--emulator` in run-unit-tests.sh 3 (>= 2); `emulators firestore start` in compose 1; `firestore:` marker in pyproject 1; `FIRESTORE_EMULATOR_HOST` in `.env.example` 0; `def build_oauth_storage` 1; `OAUTH_STORAGE_ENCRYPTION_KEY` in oauth_storage.py 2; `FileTreeStore|DiskStore` 0; `MAX_QUESTION_CHARS` 3; `class InMemoryGapLog` 1; `def test_` in test_gaplog.py 13.

## Decisions Made

See `key-decisions` in the frontmatter. Flagged assumption carried from the plan: Firestore TTL deletion is asynchronous (typically within 24 h of `expire_at`) and is not exercised by the emulator, so "90 days" means eligible for deletion after 90 days; the TTL policy itself is an infra step for plan 02-07 and Phase 4.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Docstring line over the 100-character ruff limit**
- **Found during:** Task 1 (`ruff check` in `--all`)
- **Fix:** split the module docstring into summary line plus body
- **Files modified:** `services/mcp_server/buddy_mcp/gaplog.py`
- **Commit:** `d55ac28`

**2. [Rule 3 - Blocking] mypy --strict: `reader.close()` is an untyped call**
- **Found during:** Task 1 and Task 3
- **Issue:** `google.cloud.client.Client.close` (inherited by `AsyncClient`) is a synchronous, untyped method in google-cloud-core.
- **Fix:** one-line `# type: ignore[no-untyped-call]` with a reason in the two integration tests, instead of a package-wide mypy override.
- **Files modified:** `tests/integration/test_firestore_gaplog.py`, `tests/integration/test_firestore_oauth_store.py`
- **Commits:** `d55ac28`, `3fed91f`

**3. [Rule 3 - Blocking] Formatting and a missing type annotation in the new tests**
- **Found during:** Task 2 and Task 3 GREEN gates (`ruff format --check`, mypy `var-annotated`)
- **Fix:** annotated `calls: list[int]`; ran `ruff format` on `oauth_storage.py`
- **Commits:** `d91217d`, `44252ac`

**Total deviations:** 3 auto-fixed (all Rule 3, lint or type gates). **Impact:** none on behavior or scope.

### Plan variance (not a deviation)

- The plan's conditional `[[tool.mypy.overrides]]` for `google.cloud.*` was not needed and was not added.
- Task 3 adds a second emulator test (`test_wrong_key_does_not_read_the_value`) beyond the plan's behavior list, to prove the encryption wrapper is actually keyed.

## Authentication Gates

None. The emulator needs no credentials; `.env` is passed to the test container through `env_file` and never echoed.

## Known Stubs

None. (The RED-phase stubs were replaced in the GREEN commits.)

## Threat Flags

None beyond the plan's threat model. Mitigations applied: T-02-08 (six-key document, no identity parameter, key-set and identity-pattern tests on unit and emulator), T-02-09 (Fernet mandatory for the Firestore store, ciphertext-at-rest emulator test, key only from the caller), T-02-10 (tests skipped unless the emulator host is set, project `demo-ai-buddy`, `.env.example` never sets the host, compose service has no published ports and no credentials mounted), T-02-11 (2000-character question, 10 x 200-character `tried`), T-02-SC (emulator image pinned `google/cloud-sdk:592.0.0-emulators`, no new pip packages).

## Issues Encountered

- `docker-compose.test.yml` `tests` service reads `BUDDY_ENV_FILE`, `HOST_UID` and `HOST_GID`; running `docker compose` on that file by hand without them fails. `./run-unit-tests.sh --emulator` exports them.
- py-key-value-aio emits an "unstable store" UserWarning for any configured store; it is upstream noise, not filtered.

## Next Phase Readiness

Ready for 02-04 (`buddy_report_gap` tool can take a `GapLog` and use `InMemoryGapLog` in tests), 02-05 (inject `build_oauth_storage(...)` into the OAuth proxy as `client_storage`) and 02-07 (composition root builds `FirestoreGapLog` and the OAuth store; the TTL policy `gcloud firestore fields ttls update expire_at --collection-group=gaps --enable-ttl` is documented there and applied in Phase 4).

## Self-Check: PASSED
