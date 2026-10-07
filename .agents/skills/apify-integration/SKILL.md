---
name: project-apify-integration
description: Use for any work involving Apify Actors, runs, datasets, authentication, retries, timeouts, or source connectors in this project.
---

# Apify Integration Skill

## Workflow

1. Read `docs/06-apify-integration.md` and inspect the existing Connector.
2. Keep `APIFY_API_TOKEN` in Environment only.
3. Send authentication as `Authorization: Bearer ...`; never put token in URLs.
4. Use Actor IDs with `~`, for example `compass~crawler-google-places`.
5. Validate input schema against the Actor documentation before changing fields.
6. Wait for completion, verify run status and dataset ID, then retrieve dataset items.
7. Map source fields into the domain model without losing source identity.
8. Mock HTTP in tests; never call a paid Actor from unit tests.

## Failure handling

Classify 401/403 as credential errors, 404 as Actor/endpoint errors, timeout as retryable infrastructure failure, and empty datasets as a data/query issue. Error messages must not include tokens.

## Done criteria

Tests cover request shape, auth header, dataset retrieval and malformed run responses. Documentation explains any new Actor input or output mapping.
