---
name: project-data-quality
description: Use when changing normalization, deduplication, scoring, provenance, schemas, or exports of business leads.
---

# Data Quality Skill

## Workflow

1. Inspect the current `Lead` model and storage schema before editing.
2. Normalize whitespace, empty values, URLs, phone formatting and names deterministically.
3. Prefer stable source IDs, then phone, website, coordinates, address and name similarity for matching.
4. Auto-merge only high-confidence matches; retain possible duplicates with reasons.
5. Keep source and collection time so every important value is auditable.
6. Score completeness separately from confidence; missing data is not automatically false data.
7. Add fixture-based tests for Persian text, empty fields, duplicate records and malformed source values.

## Export contract

JSON remains machine-readable and CSV remains spreadsheet/CRM-friendly. Do not silently rename existing fields; use an explicit migration when a breaking change is unavoidable.
