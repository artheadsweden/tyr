# Tyr validator (v0.5)

This folder contains the stdlib-only deterministic validator CLI.

## Command

- `python tools/tyr/tyr.py validate --stage coding|verification|ci`

## Outputs

The validator writes a deterministic report into the active intent folder:

- `.id-sdlc/intent/<folder>/validator-report.json`

## v0.5 semantics (summary)

- `allowed_paths` defines the bounding box.
- `forbidden_paths` is an overriding deny layer (deny wins, even if also allowed).
- If `development-plan.md` is missing, the validator falls back to intent-scope boundaries.
- `yellow-auto` is treated as quarantine; at governance level 2+ it is a hard failure.

## Notes

- This validator intentionally does not depend on PyYAML; it parses a small safe subset of YAML sufficient for the `.id-sdlc/*.yml` contracts in this repo.
