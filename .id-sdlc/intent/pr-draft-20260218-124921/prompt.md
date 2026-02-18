# Execution prompt

Implement the dry-run change strictly within the active intent package folder.

Binding inputs:

- `intent.md` (contract)
- `development-plan.md` (binding constraints)

Task:

- Create `.id-sdlc/intent/pr-draft-20260218-124921/implementation-summary.md`.
- Keep content short: describe what this dry-run validated (Intent→Plan→Code→Verify→Learn).

Constraints:

- Do not modify any files outside `.id-sdlc/intent/pr-draft-20260218-124921/`.
- Create exactly one git commit.

Verification hook:

- The coding commit must touch only `implementation-summary.md`.
