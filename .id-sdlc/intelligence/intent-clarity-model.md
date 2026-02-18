# Intent clarity model (v0.2)

This document defines a simple, auditable scoring model for intent clarity.

The Learner may compute an `intent_clarity_score` for a mission by applying the deductions below.
All deductions applied must be listed explicitly in the mission outcome record.

## Scoring

Start at **100**.

Deductions:

- minus 10 if acceptance criteria section is missing.
- minus 5 per acceptance criterion that is not testable/verifiable.
- minus 10 if scope boundaries are vague (example: “update auth code” without file/path constraints).
- minus 15 if expected zones are not declared.
- minus 20 if intent conflicts with zones/red-ops constraints without a manual plan.

Minimum score is 0.
