# Explainable Lead Data Quality Design

## Goal

Add field-level evidence and confidence to the existing Lead pipeline without breaking current SQLite rows or JSON/CSV consumers.

## Design

Introduce optional `field_evidence` and `field_confidence` mappings on `Lead`. Normalization preserves them and validates confidence values from 0 to 1. Existing score/completeness remain unchanged. Source identity evidence is always recorded when `source_id` or `source_url` exists; connector mappings provide confidence appropriate to their source rather than treating snippets or job descriptions as ownership evidence.

Deduplication and merge operations return or persist a reason code based on the strongest matching identity candidate (source ID, phone, domain, or address/name). Conflicting field values retain the higher-confidence value and record both source references in evidence metadata. No owner/person inference is added.

Tests cover backward-compatible construction, malformed confidence, source mapping, duplicate reason codes, conflicting merges, and unchanged export compatibility.
