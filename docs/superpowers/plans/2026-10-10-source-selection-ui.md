# Source Selection UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expose source selection in the web search form while clearly locking sources whose contracts are not enabled.

**Architecture:** Keep source capability truth in the existing registry and pass descriptors to the template. Render one accessible checkbox/card per source; only enabled sources can be selected. Preserve the existing form POST contract for Places and reject unsupported selections server-side.

**Tech Stack:** FastAPI, Jinja2, existing registry/service, pytest TestClient.

## Global Constraints

- Do not execute paid social Actors.
- Disabled sources must remain visible but non-selectable with Persian status text.
- Preserve existing Places search behavior and validation.
- Never expose credentials in UI or logs.

### Task 1: Add source descriptors to the search page

**Files:**
- Modify: `src/web/routes.py`
- Modify: `templates/search.html`
- Test: `tests/test_web_app.py`

**Interfaces:**
- The GET `/search` context includes `sources`, a list of capability descriptors with `source`, display label, `enabled`, and `reason`.
- POST `/search` continues accepting `source`; disabled selections return the existing safe 400 response.

- [ ] Add a route test asserting `/search` renders all declared sources and marks disabled sources.
- [ ] Run the focused web test and confirm it fails before implementation.
- [ ] Pass registry capabilities into the template and render source cards with checked/enabled state for Places.
- [ ] Keep disabled cards visible with `disabled` controls and explanatory Persian text.
- [ ] Run focused and full pytest suites.
- [ ] Run `git diff --check` and commit the UI change.
