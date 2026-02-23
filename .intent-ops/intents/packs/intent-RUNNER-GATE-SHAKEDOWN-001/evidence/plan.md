# intent-RUNNER-GATE-SHAKEDOWN-001 — Plan

## Repo-tracked files to change/add (exact)

Across the full lifecycle of this intent, the **only** repo-tracked files that should be changed/added are:

### Plan stage (plan commit)
1. `.intent-ops/intents/packs/intent-RUNNER-GATE-SHAKEDOWN-001/prompt.md`
2. `.intent-ops/intents/packs/intent-RUNNER-GATE-SHAKEDOWN-001/evidence/plan.md` (this file)

### Coding stage (coding commit)
3. `.intent-ops/intents/packs/intent-RUNNER-GATE-SHAKEDOWN-001/evidence/proof.md`

### Close stage (close commit)
4. `.intent-ops/intents/packs/intent-RUNNER-GATE-SHAKEDOWN-001/intent.json` (flip `status`: `open` → `closed`)

Scope check: every path above is under:
- `.intent-ops/intents/packs/intent-RUNNER-GATE-SHAKEDOWN-001/**`

## Mandatory human approval gate

This shakedown must exercise the Runner’s mandatory human approval gate before **any coding changes** are made.

- **GO**: proceed to coding stage and create `evidence/proof.md`.
- **NO-GO**: do not make coding-stage changes; stop.
- **CANCEL**: abort the run; do not make coding-stage changes.

## Validator reports (gitignored)

Validator reports are generated under:

- `.intent-ops/intents/packs/intent-RUNNER-GATE-SHAKEDOWN-001/evidence/logs/validator-report.*.json`

These files are **gitignored** and must **not** be committed.

## Validation commands (exact)

Run the validator for each stage:

- `python .intent-ops/framework/tools/validate.py --stage coding`
- `python .intent-ops/framework/tools/validate.py --stage verification`
- `python .intent-ops/framework/tools/validate.py --stage ci`

## Transaction purity notes

- **Plan commit**: ONLY
  - `.intent-ops/intents/packs/intent-RUNNER-GATE-SHAKEDOWN-001/prompt.md`
  - `.intent-ops/intents/packs/intent-RUNNER-GATE-SHAKEDOWN-001/evidence/plan.md`

- **Coding commit (GO only)**: ONLY
  - `.intent-ops/intents/packs/intent-RUNNER-GATE-SHAKEDOWN-001/evidence/proof.md`

- **Close commit**: ONLY
  - `.intent-ops/intents/packs/intent-RUNNER-GATE-SHAKEDOWN-001/intent.json`
