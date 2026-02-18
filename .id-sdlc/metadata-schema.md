# metadata.json schema (Tyr ID-SDLC v0.2)

This document defines the metadata format stored alongside each intent package under:

- `.id-sdlc/intent/<folder>/metadata.json`

## Required fields

- `artifact_schema_version` (string): Schema identifier, for example `metadata.v1`.
- `pr` (string): PR identifier or `TBD`.
- `folder` (string): The intent folder name.
- `created_by` (string): `intent.agent` | `human` | `imported`.
- `timestamp_utc` (string): ISO8601 UTC timestamp.
- `risk_class` (string): `unknown` | `low` | `medium` | `high` | `critical`.
- `zones_touched` (array of strings): Any of `green`, `yellow`, `yellow-auto`, `red`, `orange`.
- `red_operations_involved` (boolean)
- `implementation_mode` (string): `agent` | `human` | `mixed`.
- `coding_commit_sha` (string|null): The coding agent commit SHA.
- `human_commits_after_coding` (array of strings): Commit SHAs in chronological order.
- `verified_head_sha` (string|null): SHA verified by verification.
- `verification_status` (string): `READY` | `NOT_READY`.

## Optional fields

- `verification_timestamp_utc` (string|null): ISO8601 UTC timestamp of the most recent verification run.
- `runs` (array): Runtime traceability entries, for example toolchain/adaptor, model, initiator.
- `notes` (string): Freeform notes.

## runs[] entry (optional)

A run entry may include:
- `stage` (string): `intent` | `coding` | `verification` | `audit`
- `toolchain` (string): e.g. `copilot_vscode`
- `model` (string|null): e.g. `GPT-5.2`
- `initiator` (string): `human` | `automation`
- `timestamp_utc` (string): ISO8601 UTC

## Example

```json
{
  "artifact_schema_version": "metadata.v2",
  "pr": "TBD",
  "folder": "pr-draft-20260217-101006",
  "created_by": "intent.agent",
  "timestamp_utc": "2026-02-17T10:10:06Z",
  "risk_class": "unknown",
  "zones_touched": ["yellow-auto", "orange"],
  "red_operations_involved": false,
  "implementation_mode": "agent",
  "coding_commit_sha": null,
  "human_commits_after_coding": [],
  "verified_head_sha": null,
  "verification_status": "NOT_READY",
  "verification_timestamp_utc": null,
  "runs": [
    {
      "stage": "intent",
      "toolchain": "copilot_vscode",
      "model": "GPT-5.2",
      "initiator": "human",
      "timestamp_utc": "2026-02-17T10:10:06Z"
    }
  ]
}
```
