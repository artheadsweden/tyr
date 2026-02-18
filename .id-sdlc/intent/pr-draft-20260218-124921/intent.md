# Dry-run: ID-SDLC v0.2 lifecycle validation

## Title

Dry-run: generate an implementation artifact inside the intent package.

## Summary

Validate the end-to-end v0.2 lifecycle (Intent → Plan → Code → Verify → Learn) using a minimal change that stays entirely inside the active intent package.

## Strategy context (optional)

- strategy_refs:
- business_context:

## Goals

- Produce a valid `development-plan.md` that constrains execution.
- Produce exactly one Coding commit that creates `implementation-summary.md` inside this intent package.
- Produce verification artifacts (`verification.md`, `verification.json`, `evidence-chain.json`) and bind metadata fields.
- Produce local-only Learner outputs under `.id-sdlc/intelligence/`.

## Non-Goals

- No changes to governance configuration.
- No changes to application or documentation files outside this intent folder.
- No CI integration.

## Scope

Allowed changes:

- `.id-sdlc/intent/pr-draft-20260218-124921/**`
- `.id-sdlc/current-intent.json` (routing pointer update for this dry-run)

Forbidden changes:

- Any other path in the repository.

## Zone Impact

- orange: `.id-sdlc/intent/pr-draft-20260218-124921/**`, `.id-sdlc/current-intent.json`

No red operations.

## Risk Analysis

Low risk: change is confined to governance runtime artifacts only.

## Acceptance Criteria

1. `development-plan.md` exists and declares a single waypoint with explicit allowed/forbidden paths.
2. Coding stage creates exactly one git commit that adds `.id-sdlc/intent/pr-draft-20260218-124921/implementation-summary.md` and touches no other paths.
3. Verification writes:
   - `.id-sdlc/intent/pr-draft-20260218-124921/verification.md`
   - `.id-sdlc/intent/pr-draft-20260218-124921/verification.json`
   - `.id-sdlc/intent/pr-draft-20260218-124921/evidence-chain.json`
   and updates `metadata.json` with `verified_head_sha`, `verification_status`, `verification_timestamp_utc`, `coding_commit_sha`.
4. Learner writes local-only outputs:
   - `.id-sdlc/intelligence/mission-outcomes.ndjson` (append one record)
   - `.id-sdlc/intelligence/friction-zones.json` (update aggregates)

## Implementation Plan

Follow the v0.2 lifecycle stages for this intent package.

## Test Plan

- Use `git show --name-only --pretty='' <coding_commit_sha>` to confirm the coding commit touched only the declared file.
- Ensure verification artifacts and evidence chain are present and internally consistent.

## Rollback Plan

- Reset `.id-sdlc/current-intent.json` to no-active-intent.
- Optionally revert the coding commit.

## Manual Red Changes (if applicable)

None.
