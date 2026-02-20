# Path matching (v0.5)

This project uses two different pattern systems:

- Governance allow/deny patterns in `.id-sdlc/zones.yml` are **regex**.
- Intent development plan scopes (`allowed_paths`, `forbidden_paths`) are **root-anchored globs**.

This document defines the v0.5 glob semantics used by the deterministic validator.

## Normalization

All paths are normalized before matching:

- Paths are repo-root relative.
- Strip leading `./` and `/`.
- Use `/` as the separator.

## Glob language

Supported tokens:

- `*` matches any characters within a single path segment (does not cross `/`).
- `**` matches across path segments (may include `/`).
- `?` matches one character within a segment.
- Character classes like `[a-z]` are supported as a best-effort.

Patterns are **root-anchored** and must match the **entire** normalized path.

Examples:

- `README.md` matches only the repo-root `README.md`.
- `**/README.md` matches `README.md` anywhere.
- `src/**` matches anything under `src/`.

## Precedence (deny wins)

- A changed path must match at least one `allowed_paths` pattern.
- A changed path must match zero `forbidden_paths` patterns.
- If a path matches both allowed and forbidden, it is a violation (deny wins).

## Guidance

Avoid patterns like `forbidden_paths: ["**/*"]` together with a specific allow; with deny-wins this forbids everything.
