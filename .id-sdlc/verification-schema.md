# verification.json schema (Tyr ID-SDLC v0.2)

Verification artifacts live alongside each intent package under:

- `.id-sdlc/intent/<folder>/verification.md`
- `.id-sdlc/intent/<folder>/verification.json`

## Required fields

- `artifact_schema_version` (string): Schema identifier, for example `verification.v1`.
- `folder` (string): The intent folder name.
- `verified_head_sha` (string): The git SHA that was verified (typically `HEAD`).
- `timestamp_utc` (string): ISO8601 UTC timestamp.
- `verification_status` (string): `READY` | `NOT_READY`.
- `zone_violations` (array): List of zone compliance issues (empty if none).
- `red_operation_violations` (array): List of red-operation compliance issues (empty if none).
- `acceptance_summary` (array): Acceptance-criteria evaluation entries (empty if none).
- `human_commits_after_coding` (array of strings): Commit SHAs between coding commit and HEAD (empty if none).
- `notes` (string): Short explanation of the decision.

## Optional fields

- `evidence` (array): Links/commands/results captured during verification.

## Example

```json
{
  "artifact_schema_version": "verification.v2",
  "folder": "pr-draft-20260217-101006",
  "verified_head_sha": "<sha>",
  "timestamp_utc": "2026-02-17T12:00:00Z",
  "verification_status": "READY",
  "zone_violations": [],
  "red_operation_violations": [],
  "acceptance_summary": [],
  "human_commits_after_coding": [],
  "notes": "All changes are confined to the declared scope and match the intent contract."
}
```
