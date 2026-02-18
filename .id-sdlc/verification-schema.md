# verification.json schema (ID-SDLC-Imp v0.1)

Verification artifacts live alongside each intent package under:

- `id-sdlc-imp/.id-sdlc/intent/<folder>/verification.md`
- `id-sdlc-imp/.id-sdlc/intent/<folder>/verification.json`

## Required fields

- `artifact_schema_version` (string): Schema identifier, for example `verification.v1`.
- `folder` (string): The intent folder name.
- `verified_head_sha` (string): The git SHA that was verified (typically `HEAD`).
- `timestamp_utc` (string): ISO8601 UTC timestamp.
- `verification_status` (string): `pass` | `fail` | `needs_human_review`.
- `zones_summary` (object): Summary of zones affected.
- `red_operations_detected` (array): List of detected red operations by id.
- `notes` (string): Short explanation of the decision.

## Optional fields

- `human_commits_after_coding` (array of strings)
- `evidence` (array): Links/commands/results captured during verification.

## Example

```json
{
  "artifact_schema_version": "verification.v1",
  "folder": "pr-draft-20260217-101006",
  "verified_head_sha": "<sha>",
  "timestamp_utc": "2026-02-17T12:00:00Z",
  "verification_status": "pass",
  "zones_summary": {
    "green": [],
    "yellow": ["id-sdlc-imp/"],
    "yellow-auto": ["id-sdlc-imp/"],
    "red": [],
    "orange": ["id-sdlc-imp/.id-sdlc/"]
  },
  "red_operations_detected": [],
  "human_commits_after_coding": [],
  "notes": "All changes are confined to id-sdlc-imp/ and match the intent contract."
}
```
