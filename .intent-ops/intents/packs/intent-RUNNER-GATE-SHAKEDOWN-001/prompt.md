# intent-RUNNER-GATE-SHAKEDOWN-001 — Runner Gate Shakedown (Prompt)

## Objective
Exercise the Runner’s **mandatory human approval gate** such that **no coding-stage repo changes** happen until a human explicitly selects one of:

- **GO** (proceed to coding)
- **NO-GO** (do not proceed; stop)
- **CANCEL** (abort the run; stop)

## Hard constraints
- All repo-tracked changes for this intent must remain within:
  - `.intent-ops/intents/packs/intent-RUNNER-GATE-SHAKEDOWN-001/**`
- Do **not** touch:
  - `.intent-ops/framework/**`
- Minimal scope:
  - Coding stage creates **only** `evidence/proof.md`.
  - Close stage flips `status` in `intent.json` from `open` → `closed`.

## Required sequence
1. **Plan stage**: create/update only the plan artifacts listed in `evidence/plan.md`.
2. **Mandatory approval gate (before coding)**: Runner must stop and obtain human selection **GO/NO-GO/CANCEL**.
   - If **GO**: proceed to step 3.
   - If **NO-GO** or **CANCEL**: do not create `evidence/proof.md`; end run.
3. **Coding stage** (GO only): create `evidence/proof.md` stating that coding occurred only after explicit human GO.
4. **Verification/CI**: run the validator commands listed in `evidence/plan.md`.
5. **Close stage**: flip `intent.json` `status` to `closed`.
