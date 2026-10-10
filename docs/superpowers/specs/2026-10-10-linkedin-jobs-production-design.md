# LinkedIn Jobs Production Integration Design

## Goal

Activate LinkedIn Jobs as the first production-ready secondary source while preserving the existing safety gates for Instagram and TikTok. A campaign may select LinkedIn Jobs alongside Google Places and Google Search, and its public company/job data must be normalized into the existing Lead pipeline with source provenance.

## Architecture

- `ApifyClient` sends the environment-only token as an in-memory `Authorization: Bearer` header; tests assert the header without logging the token.
- `ApifyLinkedInJobsConnector` remains responsible for Actor input, run lifecycle, dataset retrieval, response classification, allowlisting, and mapping to `Lead`.
- `ConnectorRegistry` exposes a LinkedIn Jobs factory and marks the capability enabled only after its contract gate is satisfied.
- `SearchLeadsService` and `MultiSourceOrchestrator` use the same source-selection and campaign persistence path as Places and Google Search.
- Job listings become company leads. `companyName` is required; `jobId` and `jobUrl` are retained as source identity/provenance. Applicant, recruiter, reviewer, commenter, and inferred owner fields are discarded.
- Existing deduplication and scoring remain authoritative; no parallel job-specific storage model is introduced in this phase.

## Contract and rollout

The gate requires the documented Actor input (`keywords`, `location`, `maxResults`, optional detail/company flags), the observed public output allowlist, approximate pricing metadata, and the privacy policy. LinkedIn Jobs is enabled with a default maximum of five results for UI/campaign execution and a hard connector cap of 100. Instagram and TikTok remain disabled.

The UI shows source availability, preview payload, estimated result cost, and execution state. Failed LinkedIn execution must not erase successful results from other sources; the orchestration result is `partial` when appropriate.

## Error handling

401/403 are credential errors, 404 is an Actor/endpoint error, timeout/429/5xx are retryable infrastructure failures, malformed run responses are structural failures, and empty datasets are reported as a query/data issue. Error messages and persisted metadata never contain the token or raw exception text.

## Validation

- Unit tests mock Apify for authorization, request shape, successful dataset mapping, malformed records, empty datasets, and provider failures.
- Existing service, orchestration, persistence, export, UI, and privacy tests remain green.
- A controlled real smoke test uses `software engineer`, `Berlin, Germany`, and `maxResults=5`; it verifies run status, dataset identity, count, and allowlisted fields without printing credentials or raw private data.
- An end-to-end local campaign test verifies persistence, deduplication, provenance, partial failure behavior, and JSON/CSV export.
