# Production Hardening Design

## Goal

Make the existing local worker and Apify execution path recoverable and observable without adding Redis or changing the persistence model.

## Scope

- Recover expired job leases through the existing repository APIs.
- Add safe health endpoints for application, database, and worker liveness.
- Add worker shutdown that stops new claims and releases the current lease.
- Enforce existing budget reservations and add a deterministic per-job source limit before Actor execution.
- Preserve idempotency, fencing, retries, partial results, and token redaction.

## Non-goals

No external queue, authentication system, CRM integration, or social Actor activation is included.

## Safety

Recovery must use the existing fencing token and lease expiry checks. A stale worker must not update a reclaimed job. Health responses contain only booleans/status and sanitized counts. Budget or rate-limit rejection must happen before any network call.

## Validation

Add deterministic repository/worker tests for expired lease recovery, stale fencing, graceful stop, health status, budget rejection, and source limits. Run the full pytest suite and diff hygiene checks.
