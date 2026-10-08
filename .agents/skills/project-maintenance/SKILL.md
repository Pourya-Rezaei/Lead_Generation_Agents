---
name: project-maintenance
description: Use when maintaining Git history, release versioning, project documentation, or repository hygiene for this project.
---

# Project Maintenance Skill

## Workflow

1. Read `docs/README.md` and `docs/11-change-history.md` before changing project-wide documentation or repository configuration.
2. Keep `.env`, local databases, virtual environments, caches, exports and build artifacts out of Git.
3. Use Conventional Commits for repository history.
4. Record architecture, migration, compatibility, testing and security changes in `docs/11-change-history.md`.
5. Update the relevant reference/how-to document when behavior, CLI options, schema, export, Web UI, or operational workflow changes.
6. When the FastAPI/Jinja UI changes, keep its Persian RTL behavior, localhost-only boundary, route inventory, static assets and dependency requirements documented.
7. If Codebase Memory is refreshed, record the index status and keep generated graph artifacts subject to `.gitignore` and repository policy; never index or commit secrets or local databases.
8. Run the smallest relevant validation, then `pytest -q` before closing a project-wide maintenance task.
7. Never include credentials or private lead data in documentation, fixtures, logs, or commits.

## Completion checklist

- `git status` is reviewed and sensitive files are ignored.
- Documentation matches the implemented behavior, including CLI and Persian RTL Web UI.
- Generated CBM artifacts are intentionally handled and sensitive local files remain ignored.
- Tests and dependency checks pass.
- The change history records what changed, why, compatibility impact, and remaining decisions.
