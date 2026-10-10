# Production Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the local worker and Apify execution path recoverable and observable without adding an external queue.

**Architecture:** Extend the existing JobRepository lease/fencing APIs for expired-lease recovery, add a small health service and routes that expose sanitized state, and add cooperative stop behavior to Worker. Reuse existing budget reservation and source orchestration paths so all guards run before connector execution.

**Tech Stack:** Python 3.14, FastAPI, SQLite, Pydantic, pytest.

## Global Constraints

- No Redis or new runtime dependency.
- Stale workers must not update reclaimed jobs; fencing tokens remain mandatory.
- Health output contains no token, raw exception, or stack trace.
- Budget/rate-limit rejection occurs before any Apify network call.
- Preserve existing `succeeded`, `partial`, `failed`, retry, cancellation, and idempotency behavior.

---

### Task 1: Recover expired leases safely

**Files:**
- Modify: `src/execution/jobs.py`
- Test: existing execution repository test module containing lease tests

**Interfaces:**
- Consumes: `JobRepository.claim`, lease expiry, and fencing token fields.
- Produces: `recover_expired_leases(now: datetime | None = None) -> int` and stale-update rejection.

- [ ] Add a test creating a leased job with an expired lease and assert recovery returns one job and makes it claimable.
- [ ] Add a test where the old fencing token attempts an update after recovery and assert the update is rejected.
- [ ] Run the focused execution tests and confirm the new tests fail before implementation.
- [ ] Implement one transactional recovery/update path using the existing SQLite connection and current timestamp.
- [ ] Run all execution tests.

### Task 2: Add cooperative worker stop and recovery cycle

**Files:**
- Modify: `src/execution/worker.py`
- Test: worker tests

**Interfaces:**
- Consumes: `JobRepository.recover_expired_leases` and existing worker handler dispatch.
- Produces: `Worker.stop()`, `Worker.run_once()`, and a loop that stops claiming after the stop signal.

- [ ] Add tests asserting `stop()` prevents a second claim and that an expired job is recovered before the next claim.
- [ ] Implement a `threading.Event` stop flag; check it before claiming and after handler completion.
- [ ] Release or mark the current lease through the existing fenced update path during cooperative stop.
- [ ] Run worker tests and verify existing retry/cancel behavior remains unchanged.

### Task 3: Add sanitized health service and endpoints

**Files:**
- Create: `src/health.py`
- Modify: `src/web/routes.py`
- Modify: `src/web/app.py` if router registration is needed
- Test: `tests/test_web_jobs.py` or a new `tests/test_health.py`

**Interfaces:**
- Produces: `GET /health/live` with `{status: "ok"}` and `GET /health/ready` with database/worker booleans and HTTP 200/503.

- [ ] Add route tests for live success, ready success, and ready failure when the database check fails.
- [ ] Implement `HealthService.live()` and `HealthService.ready()` using a trivial SQLite query and worker state only.
- [ ] Return stable error codes such as `database_unavailable` without exposing exception text.
- [ ] Run focused web tests.

### Task 4: Enforce per-job source limits before execution

**Files:**
- Modify: `src/execution/jobs.py` or existing job validation boundary
- Modify: `src/execution/worker.py` only if validation belongs at dispatch
- Test: job and worker tests

**Interfaces:**
- Consumes: job source list and requested limit.
- Produces: deterministic validation rejecting limits below 1 or above 100 and more than three sources before connector invocation.

- [ ] Add tests that invalid limits/source counts return a stable validation error and fake connectors receive zero calls.
- [ ] Implement validation at the job submission/claim boundary, before handler dispatch.
- [ ] Preserve existing default limits and error response shape.
- [ ] Run job, worker, and API tests.

### Task 5: Document operations and validate

**Files:**
- Modify: `docs/02-operations-guide.md`, `docs/09-roadmap.md`, `docs/11-change-history.md`
- Test/command: full pytest and diff checks

**Interfaces:**
- Produces: documented recovery, health endpoints, shutdown, and source-limit behavior.

- [ ] Document `GET /health/live`, `GET /health/ready`, lease recovery, and graceful worker stop.
- [ ] Mark production hardening complete and list remaining social/auth/CRM work accurately.
- [ ] Run `PYTHONPATH=. .venv/bin/pytest -q`.
- [ ] Run `git diff --check` and verify no secrets or unrelated files are present.
