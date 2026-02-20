# change-manifest.json (v0.5)

The Coding stage must produce a change declaration artifact in the active intent folder:

- `.id-sdlc/intent/<folder>/change-manifest.json`

The deterministic validator compares this manifest to the git diff.

## Schema (change_manifest.v1)

Top-level keys:

- `artifact_schema_version`: must be `change_manifest.v1`
- `folder`: intent folder name
- `base_sha`: commit SHA before changes began
- `working_sha`: commit SHA after changes are committed; `null` for pre-commit validation
- `changed_files`: list of objects with:
  - `path`: repo-relative path
  - `change_type`: one of `A`, `M`, `D`, `R`
  - `zone_expected`: one of `green`, `yellow`, `red`, `yellow-auto`, `orange`
- `new_paths`: list of newly created directories
- `red_ops_observed`: list of red-operation ids declared by the coder
- `red_ops_uncertain`: list of “maybe” hits with reasons
- `summary`: short natural language explanation (informational only)

## Rename representation

For `change_type: R`, v0.5 uses an explicit `old -> new` string in `path`.

Example:

- `path`: `src/old_name.py -> src/new_name.py`

## Validator checks (level 3+)

- Every git diff entry appears in `changed_files` and vice versa.
- `zone_expected` matches deterministic zone mapping.
- `red_ops_observed` is a subset of validator-detected red ops (path-based).
- Any validator-detected red op must be declared in `red_ops_observed`.
- `new_paths` matches detected new directories.
