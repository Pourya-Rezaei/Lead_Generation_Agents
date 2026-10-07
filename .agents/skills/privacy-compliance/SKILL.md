---
name: project-privacy-compliance
description: Use for any feature or review involving owner names, contact details, social profiles, reviewer data, personal information, or scraping scope.
---

# Privacy and Compliance Skill

## Rules

- Collect only public, professional information clearly connected to a business.
- Do not infer ownership, identity, email, personal phone or employment from weak evidence.
- Do not enable reviewer/person extraction by default.
- Preserve source URL and confidence for human review.
- Minimize fields, avoid unnecessary retention, and never expose secrets in logs.
- If legality or authorization is unclear, pause and ask for a decision rather than expanding collection.

## Review checklist

For each new field ask: Is it public? Is it professional? Is it necessary? Is the source recorded? Can the result be wrong or harmful? If any answer is unsafe, omit the field or mark it unverified.
