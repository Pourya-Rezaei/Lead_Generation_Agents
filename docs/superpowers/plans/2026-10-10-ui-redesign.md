# Lead Workspace UI Implementation Plan

**Goal:** Simplify the Persian lead workspace without changing backend contracts.
**Architecture:** Keep FastAPI/Jinja rendering, native forms and progressive disclosure. Share responsive design tokens and navigation across existing pages.
**Tech Stack:** Jinja2, CSS, native HTML, existing job polling.

## Constraints
- Preserve routes, form names, source gates and review hooks.
- Keep Persian RTL; use logical layout properties.
- Do not call providers during verification or modify backend/database code.
- Preserve keyboard access, visible focus and reduced motion.

## Tasks
- [x] Inspect templates and run baseline web tests: 24 passed.
- [x] Implement shared shell, compact typography and responsive styles.
- [x] Simplify dashboard and search using native progressive disclosure.
- [x] Adapt campaign/history/job/source views; retain interaction hooks.
- [x] Add rendering regression tests and run full suite.
- [x] Verify desktop/mobile primary pages and local server.

## Verification
Run `.venv/bin/python -m pytest -q tests/test_web_app.py tests/test_web_jobs.py tests/test_web_profiles.py tests/test_web_export.py` after changes and `.venv/bin/python -m pytest -q` before completion. Inspect page families at desktop and mobile widths, check document overflow, form submission and keyboard access to settings. No branches or commits.

## Results
- Focused web suite: 31 passed.
- Complete suite: 272 passed, one existing Starlette/httpx deprecation warning.
- Browser checks at 390px and 1440px: primary pages had no document overflow.
- Campaign creation and empty detail view verified in isolated preview database.
- Job cancellation updated the live state and switched available actions correctly.
- Keyboard activation verified for skip link and search settings disclosure.
- Desktop dashboard and mobile search screenshots captured.
- Profile rendering/export behavior covered by existing tests; concurrent Instagram work was preserved and only shared styles applied to its form.
- Preview task: `UI preview`, http://127.0.0.1:8768, temporary database under `/tmp`.
- No provider execution or paid scraping was performed. This is not a formal WCAG certification or a usability study with children.