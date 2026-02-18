# current-intent.json schema (Tyr ID-SDLC v0.2)

This document defines the deterministic routing pointer used by all ID-SDLC agents.

Location:

- `.id-sdlc/current-intent.json`

Purpose:

- Provide a single, deterministic pointer to the active intent package.
- Prevent scanning for “latest” intent folders.

## Required keys

- `folder` (string|null)
  - The intent package folder name under `.id-sdlc/intent/`.
  - If `null`, there is no active intent. Agents must treat this as invalid routing for execution and STOP.
- `timestamp_utc` (string|null)
  - ISO8601 UTC timestamp indicating when the pointer was last written.
- `created_by` (string)
  - Who/what wrote the pointer. Expected values: `intent.agent` | `human` | `imported`.

## Optional keys

- `status` (string)
  - Optional human-friendly state marker (not used for routing). Example: `none`.

## Example

```json
{
  "folder": "pr-draft-20260218-130501",
  "timestamp_utc": "2026-02-18T13:05:01Z",
  "created_by": "intent.agent",
  "status": "active"
}
```
