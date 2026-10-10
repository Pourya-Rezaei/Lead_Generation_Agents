# Explainable Lead Data Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add field-level evidence, confidence, and explainable deduplication while preserving current Lead and export compatibility.

**Architecture:** Extend `Lead` with optional validated mappings. Keep scoring and storage schemas backward-compatible by serializing evidence in existing JSON-compatible fields where supported. Add deterministic helpers for evidence and duplicate reasons rather than replacing existing identity logic.

**Tech Stack:** Python 3.14, Pydantic, SQLite, pytest.

## Global Constraints

- Existing Lead construction and JSON/CSV exports must continue to work unchanged.
- Confidence values are decimals in `[0, 1]`.
- No owner/person inference is added.
- Existing dedup identity precedence remains source ID, phone, domain, then address/name.
- All new behavior must have deterministic unit tests.

---

### Task 1: Add validated Lead quality metadata

**Files:**
- Modify: `src/domain.py`
- Test: `tests/test_domain.py`

**Interfaces:**
- Produces: `Lead.field_evidence: dict[str, tuple[str, ...]]` and `Lead.field_confidence: dict[str, float]` with safe defaults.

- [ ] Test default construction has empty metadata and legacy serialization remains valid.
- [ ] Test confidence outside `[0, 1]` is rejected and evidence values are normalized strings.
- [ ] Add the optional fields and validators without changing required Lead fields.
- [ ] Run domain tests.

### Task 2: Generate connector provenance evidence

**Files:**
- Modify: `src/domain.py`
- Modify: `src/connectors/apify_google_search.py`
- Modify: `src/connectors/apify_linkedin_jobs.py`
- Modify: `src/connectors/apify_places.py`
- Test: connector tests

**Interfaces:**
- Produces: `field_evidence` entries for `source`, `source_id`, `source_url`, and mapped business fields; source confidence differs by verified structured field vs candidate snippet.

- [ ] Add tests for Google Search candidate confidence below verified Places/LinkedIn company fields.
- [ ] Add source identity evidence whenever source ID or URL is available.
- [ ] Keep snippets/descriptions as raw allowlisted data, never as ownership evidence.
- [ ] Run connector tests.

### Task 3: Explain deduplication and merge conflicts

**Files:**
- Modify: `src/domain.py`
- Modify: existing dedup/merge module identified by current tests
- Test: dedup and merge tests

**Interfaces:**
- Produces: `dedup_reason(left, right) -> str | None` and merge evidence preserving the higher-confidence field value.

- [ ] Test each identity precedence reason and the no-match case.
- [ ] Test conflicting website/address values choose the higher-confidence value and preserve evidence from both records.
- [ ] Implement deterministic reason codes such as `source_id_match`, `phone_match`, `domain_match`, and `address_name_match`.
- [ ] Run dedup, merge, and persistence tests.

### Task 4: Preserve exports and document quality metadata

**Files:**
- Modify: export serialization only if existing serializers omit the new fields
- Modify: `docs/09-roadmap.md`, `docs/05-data-model.md`, `docs/11-change-history.md`
- Test: export tests

**Interfaces:**
- Produces: backward-compatible JSON/CSV exports with evidence/confidence columns or JSON fields and documented semantics.

- [ ] Add round-trip tests for JSON and CSV export/import behavior.
- [ ] Document that confidence is field-level evidence quality, not ownership inference.
- [ ] Run full `PYTHONPATH=. .venv/bin/pytest -q` and `git diff --check`.
