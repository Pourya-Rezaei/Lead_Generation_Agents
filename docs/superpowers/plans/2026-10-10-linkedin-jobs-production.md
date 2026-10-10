# LinkedIn Jobs Production Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make LinkedIn Jobs a controlled production source in campaigns while preserving privacy, provenance, partial-failure semantics, and safe Apify authentication.

**Architecture:** Keep the existing connector/service/orchestrator boundaries. Add LinkedIn Jobs to the enabled registry only after its contract gate passes; map public job records to company `Lead` records and persist source identity through existing campaign/run/raw-record paths. Keep Instagram and TikTok disabled.

**Tech Stack:** Python 3.14, Pydantic, httpx, FastAPI/Jinja, SQLite, pytest.

## Global Constraints

- Keep `APIFY_API_TOKEN` in environment only and send it only as `Authorization: Bearer <token>`.
- Never include tokens, raw exceptions, applicant/recruiter/reviewer/commenter data, or owner inference in output or persistence.
- Use Actor ID `dataji~apify-linkdin-jobs` and a default execution limit of 5; connector hard cap is 100.
- Mock Apify in unit tests; execute exactly one controlled real smoke test with `maxResults=5`.
- Instagram and TikTok remain disabled.

---

### Task 1: Secure Apify client authentication

**Files:**
- Modify: `src/apify.py` constructor header initialization and request path
- Test: `tests/test_apify_client.py`

**Interfaces:**
- Consumes: `ApifyClient(token: str, ...)`
- Produces: requests with `Authorization: Bearer <token>` while preserving token redaction in errors/logs.

- [ ] Add a regression test asserting a mocked request receives `Authorization: Bearer test-token`, and asserting the token does not appear in an error string.
- [ ] Run `PYTHONPATH=. .venv/bin/pytest -q tests/test_apify_client.py` and verify the current masked-header failure is reproduced.
- [ ] Replace the placeholder masked header with an in-memory bearer header; do not serialize or log the token.
- [ ] Run the focused test and then `PYTHONPATH=. .venv/bin/pytest -q tests/test_apify_client.py`.

### Task 2: Complete LinkedIn Jobs connector contract tests

**Files:**
- Modify: `src/connectors/apify_linkedin_jobs.py`
- Modify: `tests/test_linkedin_jobs_connector.py`

**Interfaces:**
- Consumes: `search(query: str, location: str, limit: int = 20) -> SearchResult`
- Produces: allowlisted records and Leads with `source="apify_linkedin_jobs"`, `source_id=jobId`, and `source_url=jobUrl`.

- [ ] Add mocked tests for empty datasets, missing dataset IDs, failed runs, and limit capping.
- [ ] Assert malformed URLs/records are discarded without leaking raw data.
- [ ] Implement only the minimal changes needed to satisfy those tests.
- [ ] Run `PYTHONPATH=. .venv/bin/pytest -q tests/test_linkedin_jobs_connector.py`.

### Task 3: Enable contract-gated LinkedIn Jobs source

**Files:**
- Modify: `src/contract_gate.py`
- Modify: `src/registry.py`
- Modify: `src/connectors/social_profiles.py`
- Modify: `src/social_service.py`
- Test: `tests/test_social_profiles.py`, `tests/test_social_service.py`, `tests/test_registry.py`

**Interfaces:**
- Consumes: `ContractGateReport`, `ConnectorRegistry.validate_source/select_sources/create`.
- Produces: `linkedin_jobs` as the only enabled social/job source after schema, privacy, and pricing gates pass.

- [ ] Add a test requiring the LinkedIn input fields (`keywords`, `location`, `maxResults`, `scrapeDetails`, `scrapeCompany`) and output allowlist.
- [ ] Add a test confirming Instagram/TikTok still raise `DisabledSourceError`.
- [ ] Set only LinkedIn Jobs gate fields to verified with documented pricing and privacy exclusions.
- [ ] Mark the registry capability enabled and retain the existing connector factory.
- [ ] Run the focused registry and contract tests.

### Task 4: Integrate orchestration and campaign persistence

**Files:**
- Modify: `src/service.py`
- Modify: `src/orchestration.py`
- Modify: `src/execution/worker.py` if source dispatch requires it
- Test: `tests/test_orchestration.py`, relevant service/worker tests

**Interfaces:**
- Consumes: enabled source capability and `ApifyLinkedInJobsConnector.search`.
- Produces: campaign-scoped Lead persistence, per-source status, run/dataset metadata, and `partial` state when another source fails.

- [ ] Add a deterministic orchestration test selecting `places`, `google_search`, and `linkedin_jobs` with fake connectors.
- [ ] Assert successful Leads remain when LinkedIn Jobs fails and that source state contains a safe error code.
- [ ] Wire LinkedIn Jobs through the same service persistence path as existing Apify sources.
- [ ] Preserve deduplication, scoring, and raw-record provenance.
- [ ] Run orchestration, service, worker, and persistence tests.

### Task 5: Add controlled UI selection and preview

**Files:**
- Modify: `templates/search.html`
- Modify: `src/web/routes.py`
- Test: `tests/test_web_app.py`

**Interfaces:**
- Consumes: registry capabilities and source selection API.
- Produces: visible LinkedIn Jobs option, disabled social options, preview payload, default limit 5, and safe error status codes.

- [ ] Add route tests for selecting LinkedIn Jobs and rejecting disabled Instagram/TikTok.
- [ ] Render the LinkedIn Jobs label, approximate cost, and limit-5 default in Persian/RTL UI.
- [ ] Ensure preview never executes an Actor and execution errors do not expose tokens or raw exceptions.
- [ ] Run the focused web tests.

### Task 6: End-to-end persistence and exports

**Files:**
- Modify: existing campaign/export modules only where required
- Test: add or modify `tests/test_campaigns.py`, `tests/test_exports.py`, `tests/test_orchestration.py`

**Interfaces:**
- Consumes: orchestrated LinkedIn result with provenance.
- Produces: deduplicated SQLite campaign records and valid JSON/CSV exports containing public company/job source identity.

- [ ] Add a fake end-to-end campaign test with two jobs for one company and one distinct company.
- [ ] Assert deduplication, `source_id`, `source_url`, score/completeness, and export headers/content.
- [ ] Add a partial-failure case and assert successful source records remain persisted.
- [ ] Run all related persistence/export tests.

### Task 7: Documentation and real smoke validation

**Files:**
- Modify: `docs/06-apify-integration.md`, `docs/README.md`, `README.md`, `docs/11-change-history.md`
- Test/command: controlled Apify smoke script or one-off command

**Interfaces:**
- Consumes: enabled production behavior and verified Actor metadata.
- Produces: accurate operational documentation and evidence of one real run.

- [ ] Update documentation to state LinkedIn Jobs is enabled, its exact input/output allowlist, cost estimate, default limit, and remaining disabled sources.
- [ ] Run the real Actor once with `software engineer`, `Berlin, Germany`, `maxResults=5`; print only status, run ID, dataset ID, count, and allowlisted field names.
- [ ] Verify the dataset has five records and no credential appears in captured output.
- [ ] Run `PYTHONPATH=. .venv/bin/pytest -q`, then `git diff --check`.

### Task 8: Final review

- [ ] Inspect `git diff` for unrelated changes and secret leakage.
- [ ] Confirm full suite passes and report the exact command/result.
- [ ] Commit all implementation and documentation changes with a Conventional Commit message and the required Copilot co-author trailer.
