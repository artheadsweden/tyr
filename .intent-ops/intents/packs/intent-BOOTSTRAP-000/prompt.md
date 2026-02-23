# Bootstrap Intent: IntentOps install

Goal: Install the IntentOps governance scaffolding in this repository.

Constraints:
- Do not modify host project source code.
- Only touch:
  - .intent-ops/**
  - .github/agents/intentops.*.agent.md

Deliverables:
- Base framework configuration files in .intent-ops/framework/config/
- current-intent.json pointing to this pack
- Runner agent in .github/agents/
- Validation tooling placeholder (validate.py may be empty for now)

Acceptance:
- A diff showing only IntentOps footprint changes.