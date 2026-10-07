---
name: project-maintenance
description: Use when maintaining Git history, release versioning, project documentation, or repository hygiene for this project.
---

# Project Maintenance Skill

## Workflow

1. Read `doc/README.md` and `doc/11-change-history.md` before changing project-wide documentation or repository configuration.
2. Keep `.env`, local databases, virtual environments, caches, exports and build artifacts out of Git.
3. Use Conventional Commits for repository history.
4. Record architecture, migration, compatibility, testing and security changes in `doc/11-change-history.md`.
5. Update the relevant reference/how-to document when behavior, CLI options, schema, export, or operational workflow changes.
6. Run the smallest relevant validation, then `pytest -q` before closing a project-wide maintenance task.
7. Never include credentials or private lead data in documentation, fixtures, logs, or commits.

## Completion checklist

- `git status` is reviewed and sensitive files are ignored.
- Documentation matches the implemented behavior.
- Tests and dependency checks pass.
- The change history records what changed, why, compatibility impact, and remaining decisions.
