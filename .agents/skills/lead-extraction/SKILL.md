---
name: project-lead-extraction
description: Use when designing searches, extracting local businesses, selecting query/location inputs, or adding a lead source to this application.
---

# Lead Extraction Skill

## Workflow

1. Define the target city, country/region, occupation and desired result count.
2. Prefer precise occupational terms and local-language synonyms.
3. Start with a small limit and expand only after validating result quality.
4. Preserve business name, address, phone, website, rating, review count and source.
5. Treat social profiles and person names as unverified until evidence connects them to the business.
6. Never infer private ownership from a name, phone number or weak similarity.
7. Return a partial result with evidence when one source fails; do not silently discard the run.

## Query quality

For ambiguous occupations, use multiple explicit synonyms in separate searches and deduplicate later. For large cities, split by district when coverage matters more than latency.
