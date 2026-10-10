# Execution Reliability Findings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Resolve the seven reviewed execution, privacy, aggregation, and documentation findings without using a live Apify Actor.

**Architecture:** Keep retries for safe reads while making Actor start a single-attempt operation with ambiguous outcomes routed to the existing `needs_review` workflow. Preserve connector status and cancellation intent through the worker lifecycle, minimize raw Places data, define deterministic multi-source aggregation, and refresh current-state docs.

**Tech Stack:** Python 3.10–3.14, pytest, SQLite, httpx mocks, FastAPI application services.

## Global Constraints

- Keep `APIFY_API_TOKEN` in environment only; tests must not use real credentials.
- Never call paid Actors in tests; mock all Apify HTTP calls.
- Do not persist reviewer text/person data; retain business review counts only where already supported.
- Preserve existing public APIs, default behavior, SQLite schema, and lineage unless a targeted regression requires a narrow change.
- Preserve the pre-existing working-tree change in `docs/11-change-history.md`; do not stage or revert it.

---

## File map

- `src/apify.py`: HTTP retry classification and actor start operation.
- `src/execution/handlers.py`: provider callbacks, Places handler result-state propagation, multi-source aggregation.
- `src/execution/service.py`, `src/execution/jobs.py`, `src/execution/worker.py`: cancellation race, ambiguous start state, and terminal status precedence.
- `src/connectors/apify_places.py`, `src/storage.py`: Places field minimization and persistence verification.
- `src/orchestration.py`: deterministic aggregate status for all source result combinations.
- `tests/test_apify_client.py`, `tests/test_provider_lifecycle.py`, `tests/test_worker_recovery.py`, `tests/test_orchestration.py`, `tests/test_connectors.py` (and existing related test modules): regression coverage.
- `docs/09-roadmap.md`, `docs/13-agent-project-understanding.md`: current-state documentation.
- `docs/11-change-history.md`: final entry for behavior/test/doc changes; preserve existing user change.

### Task 1: Prevent duplicate Actor starts and preserve ambiguous outcomes

**Files:**
- Modify: `src/apify.py`
- Modify: `src/execution/handlers.py`
- Modify: `src/execution/worker.py`
- Test: `tests/test_apify_client.py`
- Test: `tests/test_provider_lifecycle.py` or the existing worker/provider lifecycle test module

**Interfaces:**
- `ApifyClient.start_actor(...)` remains the caller-facing method and keeps its return type.
- A distinct internal start-request path must not retry after a timeout, connection loss, or provider response whose acceptance is uncertain.
- The existing `needs_review` job state and error code `ProviderStartOutcomeUnknown` remain the recovery contract.

- [x] **Step 1: Add the Actor-start timeout regression.** Use a respx/httpx mock that raises `ReadTimeout` on `POST /acts/.../runs`; assert one POST and an exception/typed outcome that differentiates unknown acceptance from a definitive provider rejection. Keep an adjacent GET timeout test proving safe GET retries still work.
- [x] **Step 2: Run the targeted test and confirm it fails against current behavior.** Run `PYTHONPATH=. uv run --python 3.14 --no-project --with-editable . --with pytest --with respx pytest tests/test_apify_client.py -q`.
- [x] **Step 3: Add a worker-level regression for unknown start acceptance.** Use a fake service/connector raising the typed ambiguous-start outcome after the existing `starting` attempt is persisted; assert final job is `needs_review`, the provider attempt is retained as unresolved, and no second start is issued.
- [x] **Step 4: Implement a one-attempt Actor-start request and map ambiguous transport/status failures to the existing needs-review path.** Do not alter retry policy for idempotent GETs; preserve definitive 401/403/404 handling as ordinary credential/endpoint failures.
- [x] **Step 5: Run targeted Apify and lifecycle tests and confirm they pass.**

### Task 2: Preserve source failure and correct cancellation finalization/race

**Files:**
- Modify: `src/execution/handlers.py`
- Modify: `src/execution/service.py`
- Modify: `src/execution/jobs.py` only if an atomic repository helper is needed
- Modify: `src/execution/worker.py`
- Test: `tests/test_provider_lifecycle.py`
- Test: `tests/test_worker_recovery.py`

**Interfaces:**
- Handler output continues to include `run_ids` and references and additionally provides a canonical worker state for failed, aborted, timed-out, or partial search outcomes.
- Existing `JobService.cancel(job_id, abort_provider_run)` remains the cancellation entry point.
- Provider-run persistence stays fenced by job/worker/fencing token.

- [x] **Step 1: Add a failing `places_handler` test for `SearchResult(status=FAILED)` and assert the returned worker state is failed; add coverage for aborted, timed-out, and partial.**
- [x] **Step 2: Add a failing worker test that invokes real finalization for `cancel_requested` plus provider `aborted` and asserts `cancelled`; remove the current dead conditional that skips finalization.**
- [x] **Step 3: Add a deterministic cancellation/start race test.** Use synchronization events in a fake provider: pause after `start_actor` begins but before it returns the run ID; call cancel; release start; assert the persisted run is aborted after callback registration and the job ends cancelled.
- [x] **Step 4: Implement explicit result-state propagation from Places handler into worker terminalization.** Ensure provider failure does not silently use the default succeeded state.
- [x] **Step 5: Implement a post-persistence cancellation recheck in the provider callback.** If cancellation is requested after the run ID becomes available, invoke the abort callback exactly once; keep persistence fenced and handle abort errors without reporting success.
- [x] **Step 6: Make cancellation intent take precedence over an `aborted` provider result during finalization.** Do not overwrite independently failed jobs as cancelled.
- [x] **Step 7: Run lifecycle and worker recovery tests; verify cancellation without a known run does not call provider prematurely.**

### Task 3: Remove review content from Places storage and preserve only aggregate count

**Files:**
- Modify: `src/connectors/apify_places.py`
- Modify: `docs/06-apify-integration.md`
- Test: `tests/test_connectors.py`
- Test: `tests/test_domain_storage.py` or the closest raw-record persistence test

**Interfaces:**
- The connector still maps the aggregate numeric `reviewsCount` into the existing business review-count field.
- Raw record fields remain allowlisted; reviewer names, profile identifiers, and review text are excluded.

- [x] **Step 1: Add a connector fixture containing `reviewsCount` plus a `reviews` list with synthetic reviewer text/identifier.** Assert the business model retains only the numeric count and the raw record excludes `reviews`.
- [x] **Step 2: Run the targeted test and confirm current behavior fails because `reviews` is allowlisted or used as a fallback value.**
- [x] **Step 3: Remove `reviews` from the raw allowlist and remove the raw `reviews` fallback from the domain mapping; retain `reviewsCount` only.**
- [x] **Step 4: Run connector and persistence tests and verify no raw reviewer fields survive serialization/cache replay.**

### Task 4: Define deterministic multi-source partial aggregation

**Files:**
- Modify: `src/orchestration.py`
- Modify: `src/execution/handlers.py` only if orchestration status mapping is performed there
- Test: `tests/test_orchestration.py`
- Test: `tests/test_worker_recovery.py`

**Interfaces:**
- Aggregate status is one of the existing canonical states: `succeeded`, `partial`, or `failed`.
- All sources succeeded → `succeeded`; at least one source has usable output but results are incomplete/mixed → `partial`; no source has usable output → `failed`.

- [x] **Step 1: Add table-driven failing tests for all-succeeded, all-failed, one-partial-only, partial-plus-failed, succeeded-plus-failed, and no usable output.**
- [x] **Step 2: Implement the aggregate rule while preserving merged leads, observations, raw references, and existing source-level status details.**
- [x] **Step 3: Run orchestration and multi-source worker tests.**

### Task 5: Synchronize current-state documentation and validate the full suite

**Files:**
- Modify: `docs/README.md`
- Modify: `docs/09-roadmap.md`
- Modify: `docs/13-agent-project-understanding.md`
- Modify: `docs/11-change-history.md`

- [x] **Step 1: Replace outdated current schema/test counts in the roadmap with verified values and separate historical milestones from current status.** Confirm currently active sources and blocked/disabled sources from code/config before documenting them.
- [x] **Step 2: Refresh the agent project-understanding guide to describe the current job queue/worker, source handlers, web surface, and test baseline; remove claims contradicted by current code.**
- [x] **Step 3: Add a concise change-history entry for Actor-start ambiguity, cancellation/status fixes, raw review minimization, aggregate partial semantics, and documentation refresh. Preserve the existing unrelated entry already in that file.
- [x] **Step 4: Run targeted tests for all changed modules, then the full local suite with `PYTHONPATH=. uv run --python 3.14 --no-project --with-editable . --with pytest --with respx pytest -q`.**
- [x] **Step 5: Run `git diff --check`; inspect `git status --short`; confirm no credentials, databases, or generated artifacts are staged and the pre-existing change-history edit remains intact.**
- [x] **Step 6: Review final diff against all seven findings and report exact test command/result and any remaining limitations.**
