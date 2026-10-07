---
name: project-python-testing
description: Use for every Python code change, bug fix, connector change, schema change, or export change in this project.
---

# Python Testing Skill

## Workflow

1. Run the smallest relevant existing test first.
2. Add a regression test before or alongside a bug fix.
3. Mock Apify/network calls and use deterministic fixtures.
4. Test both successful and malformed/empty responses.
5. Run the complete local suite with `pytest -q` before reporting completion.
6. Report the exact command and result.

## Required coverage areas

- CLI validation and source selection
- Actor request and dataset mapping
- normalization and scoring
- SQLite round-trip and upsert
- JSON/CSV export
- credential and timeout failures

Never use a real API token in tests.
