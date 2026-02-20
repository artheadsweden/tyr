Below is a Copilot readable development plan for Tyr and Var, starting at v0.5 and then extending through v0.6, v0.7, v0.8. It is written to be usable in a fresh chat with no prior context, and it assumes the repository layout and contracts currently present in `artheadsweden/tyr` (agents under `.github/agents/`, governance under `.id-sdlc/`). ([GitHub][1])

It is intentionally strict. Where strictness risks blocking adoption, the plan adds explicit levels and profile switches so teams can start small and grow.

---

# Tyr and Var development plan (v0.5 → v0.8)

## 0. Purpose

This document defines a staged upgrade plan for the ID-SDLC reference implementation.

It introduces:

1. Var: a lightweight profile (intent+plan combined, coder, verifier)
2. Tyr: the full profile (intent, planner, coder, verifier, learner, auditor)
3. A deterministic validator CLI that is static code, not an agent
4. A change manifest produced by the Coding agent to make validation and human review simpler
5. A knowledge system that supports local, team, and company wide sharing
6. CI integration so the lifecycle closes the loop into “knowledge” and reduces drift over time

Non-goals for this document:

1. Cryptographic signing and attestations (explicitly postponed)
2. Mandating OKR and strategy inputs (optional only)

## 1. Current baseline (what exists today)

Repository structure and lifecycle expectations:

1. Agents exist under `.github/agents/` for intent, planner, coding, verification, learner, governance auditor. ([GitHub][1])
2. Governance is defined under `.id-sdlc/` including:

   1. governance-config.yml
   2. zones.yml
   3. red_operations.yml
   4. routing pointer current-intent.json
   5. schemas for current-intent, metadata, verification ([GitHub][1])
3. A dry run intent package exists and demonstrates the current artifact shape. ([GitHub][2])

Observed friction in the current dry run shape (these inform v0.5 priorities):

1. The plan encodes forbidden_paths as “**/*” while also declaring allowed_paths, but there is no deterministic rule defined for how conflicts resolve. ([GitHub][3])
2. The system relies heavily on agents “doing the right thing” because there is no static validator implementation in the repo yet.
3. yellow-auto is structurally dangerous for new folders because “new” does not imply “safe”. This needs explicit quarantine rules and a deterministic handling path. ([GitHub][4])
4. red-ops is language agnostic by design, which is correct, but it means enforcement must be scoped to what static code can actually prove (paths, file types, declared operations), and everything else must fail closed or be delegated to a declared plugin.

## 2. Core design decision for v0.5+: deterministic validator is static code

Answering your earlier question directly:

The deterministic validator should be static code (a CLI) that:

1. Reads declared governance and declared intent artifacts
2. Reads the actual git diff or commit range
3. Produces a deterministic pass or fail report with explicit reasons

It is not an agent. Agents can call it, but they cannot replace it.

Why:

1. Determinism requires the same inputs to always produce the same output
2. Agents are goal oriented and adaptive, which is good for planning and coding, but weak as a referee
3. A static validator is the only component that can be trusted as a “hard stop” that does not negotiate

Agents still matter because:

1. Only an agent can interpret meaning, language, intent ambiguity, and unknown unknowns
2. The validator should check what is provable, and force humans or agents to explicitly declare everything else

## 3. Profiles and levels

### 3.1 Profiles (Var vs Tyr)

Profile controls which stages are expected and which artifacts are required.

1. profile: var

   1. Combined Intent and Plan stage (single agent)
   2. Coding
   3. Verification
   4. Learner optional, off by default
2. profile: tyr

   1. Intent
   2. Planner
   3. Coding
   4. Verification
   5. Learner
   6. Governance audit

Implementation mechanism:

1. Add `profile` to `.id-sdlc/governance-config.yml`
2. Add `.id-sdlc/profiles/var.yml` and `.id-sdlc/profiles/tyr.yml`
3. Validator reads profile to decide which artifacts are required

### 3.2 Levels (adoption ramp)

Level controls strictness and scope of enforcement.

Proposed levels:

1. level 1: routing + intent contract

   1. Enforce current-intent pointer validity
   2. Enforce intent package structure
   3. Enforce that coding only touches allowed_paths declared in intent scope boundaries (coarse)
2. level 2: zones and orange safety

   1. Enforce zones.yml classification for changed files
   2. Enforce orange allowlist and denylist deterministically
   3. Enforce yellow-auto quarantine rules
3. level 3: red-ops plus change manifest

   1. Enforce red operations via path based matching
   2. Require coding agent produced change-manifest.json
   3. Enforce that manifest matches the actual diff
4. level 4: learner and CI knowledge loop

   1. Require mission outcome record
   2. Produce knowledge deltas suitable for team consumption
   3. CI gates merges on validator success

This lets a team start with Var at level 1 or 2, then later move to Tyr at level 3 or 4.

## 4. Knowledge system requirements

You asked for:

1. Knowledge shared between team members in a repo
2. Knowledge shared company wide across many repos
3. A way to manually insert knowledge

The design needs three tiers:

### 4.1 Local tier (personal, not committed)

Path: `.id-sdlc/intelligence/local/`

1. Individual friction notes
2. Per user mission outcomes
3. Scratch findings

Default: gitignored

### 4.2 Team tier (project shared, committed)

Path: `.id-sdlc/intelligence/team/`

1. Project policies and patterns
2. Project lessons learned that should travel with the repo
3. Known risky modules and their handling

Default: committed

### 4.3 Company tier (org shared, importable)

Path options:

1. External path, referenced from governance-config.yml
2. Git submodule under `.id-sdlc/intelligence/company/` (optional)

Company tier is treated as read only by agents. Only humans maintain it.

Manual insertion must be first class:

1. `tyr knowledge add` should create a new entry with frontmatter and a stable id
2. `tyr knowledge compile` should produce a single compiled file that agents can read quickly

## 5. v0.5: determinism foundation release

Theme: stop relying on “agent goodwill” by adding a validator and a change manifest.

### 5.1 v0.5 deliverables

1. Deterministic validator CLI
2. Change manifest artifact
3. Clear conflict resolution rules for allowed_paths vs forbidden_paths
4. yellow-auto quarantine enforcement rules
5. Coding stage feedback loop: validator fail triggers rollback and a replan attempt log
6. Unified profile and level settings in governance config

### 5.2 v0.5 file changes

Add new files:

1. `tools/tyr/tyr.py`
2. `tools/tyr/README.md`
3. `.id-sdlc/profiles/var.yml`
4. `.id-sdlc/profiles/tyr.yml`
5. `.id-sdlc/change-manifest-schema.md` (or .json schema)
6. `.id-sdlc/policies/path-matching.md` (defines how patterns are interpreted)
7. Update agent prompts to require manifest and validator call (details below)

Manual human change required before merge:

1. Update `.id-sdlc/zones.yml` to classify `tools/` as yellow (otherwise it becomes yellow-auto). This is a governance file and should not be changed by agents. ([GitHub][4])

### 5.3 v0.5 deterministic validator CLI specification

Command name:

1. `python tools/tyr/tyr.py validate`

Modes:

1. `validate --stage coding`

   1. Validates staged or working tree diff against plan and governance
2. `validate --stage verification`

   1. Validates HEAD, generates machine report, and supports verifier output
3. `validate --stage ci`

   1. Same as verification but prints CI friendly output and exit codes only

Inputs:

1. `.id-sdlc/governance-config.yml`
2. `.id-sdlc/zones.yml`
3. `.id-sdlc/red_operations.yml`
4. `.id-sdlc/current-intent.json`
5. Active intent folder artifacts:

   1. intent.md
   2. metadata.json
   3. development-plan.md (optional depending on profile and level)
   4. change-manifest.json (required at level 3+)

Deterministic outputs:

1. `.id-sdlc/intent/{folder}/validator-report.json`
2. `.id-sdlc/intent/{folder}/validator-report.md` (optional but recommended)

Exit codes:

1. 0: pass
2. 10: routing invalid (current-intent missing or invalid)
3. 20: artifact contract invalid (missing required intent files)
4. 30: zone violation
5. 40: red operation violation
6. 50: plan violation (changed file outside allowed_paths, or forbidden_paths match)
7. 60: yellow-auto quarantine violation
8. 70: manifest mismatch (manifest does not match diff)
9. 80: unknown enforcement semantics encountered (fail closed)

Pattern resolution rules (v0.5 must define these explicitly):

1. allowed_paths is the primary bounding box

   1. Any file changed outside allowed_paths is a violation
2. forbidden_paths is an additional deny layer

   1. Any file changed that matches forbidden_paths is a violation even if also in allowed_paths
3. If development-plan is absent (Var level 1), validator uses intent scope boundaries as allowed_paths

This resolves the ambiguity seen in the dry run plan. ([GitHub][3])

### 5.4 v0.5 change-manifest.json specification

Produced by Coding agent, stored in active intent folder:
`.id-sdlc/intent/{folder}/change-manifest.json`

Goals:

1. Give the validator an explicit declaration of what the coder believes it changed
2. Make it easy for humans to spot lies or omissions by comparing manifest and diff
3. Help red-ops enforcement without requiring language specific parsing

Minimum fields:

1. artifact_schema_version: `change_manifest.v1`
2. folder
3. base_sha (the sha before changes began)
4. working_sha

   1. if stage is pre-commit, set to null
5. changed_files

   1. list of paths with:

      1. path
      2. change_type (A M D R)
      3. zone_expected (green yellow red yellow-auto orange)
6. new_paths

   1. list of directories created
7. red_ops_observed

   1. list of operation ids from red_operations.yml that the coder believes applies
8. red_ops_uncertain

   1. list of “maybe” hits with reasons
9. summary

   1. short natural language explanation, strictly informational

Validator checks:

1. Every file in git diff must appear in changed_files
2. Every file in changed_files must appear in git diff
3. zone_expected must match deterministic zone mapping from zones.yml
4. red_ops_observed must be a subset of path based matches from red_operations.yml, unless plugins are enabled
5. If validator detects a red op by path match and manifest does not declare it, fail at level 3+

### 5.5 v0.5 yellow-auto quarantine rules

Strict rule set (default at level 2+):

1. If any new directory is created and is not already under a classified parent path in zones.yml, it is yellow-auto
2. Any change touching yellow-auto is allowed only if:

   1. the intent explicitly lists the new paths
   2. the plan includes a waypoint for “classification required”
   3. the coding agent produces `new-paths-yellow-auto.md` describing proposed classifications and why
3. Merging is blocked until zones.yml is updated by a human to classify the new folders

This directly addresses the problem you raised: “yellow-auto can secretly contain a mix of green, yellow, red”. The answer is: treat yellow-auto as quarantine, not as a zone.

### 5.6 v0.5 coding stage rollback and replan loop

This implements your idea:

1. Coding agent makes changes
2. Coding agent produces change-manifest.json
3. Coding agent calls `tyr validate --stage coding`
4. If validation fails:

   1. Coding agent must hard reset the repo to base_sha
   2. Coding agent must write a failed attempt record:
      `.id-sdlc/intent/{folder}/coding-attempts/attempt-001/`

      1. manifest.json
      2. validator-report.json
      3. failure-notes.md
   3. Coding agent must request a new plan adjustment, including how to avoid the failure next time

Important: this loop must be bounded.

1. governance-config.yml should include `max_coding_attempts: 3`
2. After max attempts, STOP and require human intervention

### 5.7 v0.5 agent updates

Update `.github/agents/id-sdlc-coding.agent.md`:

1. Require creating change-manifest.json before committing
2. Require calling validator
3. If validator fails, rollback and create coding-attempt record, then handoff to planner

Update `.github/agents/id-sdlc-verification.agent.md`:

1. Always call validator in verification mode
2. Verifier output must embed validator-report.json summary into verification.json evidence section

Update `.github/agents/id-sdlc-planner.agent.md`:

1. Plan must declare allowed_paths, forbidden_paths, expected_zones per waypoint
2. Planner must declare if yellow-auto classification is expected

Update `.github/agents/id-sdlc-intent.agent.md`:

1. Fix internal contradictions around coding_commit_sha binding by defining that coding_commit_sha is bound during verification, and verifier writes it into metadata and optionally commits orange evidence (see v0.7 for persistence strategy)

The existing contracts already point in this direction, but the validator makes it enforceable. ([GitHub][5])

## 6. v0.6: Var implementation + shared knowledge tiers

Theme: make adoption easier (Var) while expanding what “learning” means (team and company tiers).

### 6.1 v0.6 deliverables

1. Var profile implemented as a first class mode
2. Knowledge tiers implemented with compilation and manual insertion
3. Shared features between Var and Tyr, enforced via profile and level settings
4. Subagent usage conventions documented for clean context boundaries

Subagents rationale:

1. Subagents run in isolated context windows in VS Code, reducing “context carry over” and helping enforce stage separation. ([code.visualstudio.com][6])

### 6.2 v0.6 file changes

Add:

1. `.github/agents/var.agent.md` (combined intent and plan)
2. `.github/agents/var-coding.agent.md` (could reuse tyr coding, but separate lets you lock behavior)
3. `.github/agents/var-verification.agent.md`
4. `.id-sdlc/intelligence/local/.gitkeep`
5. `.id-sdlc/intelligence/team/README.md`
6. `.id-sdlc/intelligence/company/README.md`
7. `.id-sdlc/knowledge-entry-schema.md`
8. Extend validator to ingest compiled knowledge

Update:

1. `.gitignore` to ignore only `.id-sdlc/intelligence/local/` not team tier
2. `.id-sdlc/governance-config.yml` add:

   1. profile
   2. level
   3. knowledge_sources:

      1. local_path
      2. team_path
      3. company_path_external (optional)
   4. max_coding_attempts

### 6.3 v0.6 CLI commands

Add:

1. `python tools/tyr/tyr.py knowledge add`

   1. Creates `.id-sdlc/intelligence/team/entries/{id}.md` by default
2. `python tools/tyr/tyr.py knowledge compile`

   1. Compiles all knowledge sources into:
      `.id-sdlc/intelligence/team/compiled-knowledge.json`
3. `python tools/tyr/tyr.py knowledge export`

   1. Exports a zip or folder for sharing company wide
4. `python tools/tyr/tyr.py knowledge import`

   1. Imports a pack into team tier

## 7. v0.7: learner, persistence, and CI integration

Theme: complete the loop Patrick described: delivery becomes knowledge and knowledge changes future delivery.

### 7.1 v0.7 deliverables

1. CI workflow that runs validator as a required check
2. Learner output that creates both:

   1. local analytics (personal)
   2. team suggestions (commit ready deltas)
3. A mission outcome record that is always produced when a run reaches verification READY

### 7.2 CI integration (GitHub Actions)

Add `.github/workflows/tyr-validate.yml`:

1. Runs on pull_request
2. Steps:

   1. checkout
   2. run `python tools/tyr/tyr.py validate --stage ci`
3. Uploads validator-report.json as a build artifact even on failure

Validator in CI must:

1. Fail closed if routing pointer is missing or invalid
2. Fail closed if profile and level requirements are unmet
3. Fail closed if new yellow-auto paths are present without classification rule satisfaction

### 7.3 Learner integration outputs

Learner writes:

1. `.id-sdlc/intelligence/local/mission-outcomes.ndjson` (append only, gitignored)
2. `.id-sdlc/intelligence/team/learned-suggestions/{folder}/`

   1. friction-zones.delta.json
   2. policy-notes.md
   3. suggested-questions.md for future intents

The intent is: learner produces suggestions, not governance edits.

## 8. v0.8: governance evolution without breaking determinism

Theme: audits and evolution, but never self mutating governance.

### 8.1 v0.8 deliverables

1. Governance auditor outputs patch proposals as files, never direct edits:

   1. `.id-sdlc/audit/{timestamp}/zones.patch`
   2. `.id-sdlc/audit/{timestamp}/red_operations.patch`
2. A “governance review queue” format so humans can process proposals consistently
3. Optional automation script to open a PR with proposals (off by default)

---

# Copilot implementation instructions (how to use this doc)

If you are Copilot Agent Mode implementing this plan:

1. Treat v0.5 as the current milestone and implement only v0.5 scope unless explicitly asked for v0.6+
2. Do not invent new governance semantics without writing them into a policy file under `.id-sdlc/policies/`
3. Always add deterministic tests for validator behavior using only the standard library (suggested: Python unittest)
4. When you need a governance file change (zones.yml, red_operations.yml, governance-config.yml), stop and ask the human, because agents should not modify those per the current orange denylist model. ([GitHub][4])
5. Use subagents for discovery tasks when implementing complex changes, to keep your main working context small and to reduce leakage between lifecycle phases. ([code.visualstudio.com][6])

---

If you want, I can now turn v0.5 into an implementation checklist that is literally ordered as “commit sized steps”, including the exact file scaffolding for `tools/tyr/tyr.py`, the validator-report.json schema, and the first set of unit test fixtures based on your existing dry-run intent package.

[1]: https://raw.githubusercontent.com/artheadsweden/tyr/main/README.md "raw.githubusercontent.com"
[2]: https://raw.githubusercontent.com/artheadsweden/tyr/main/.id-sdlc/intent/pr-draft-20260218-124921/intent.md "raw.githubusercontent.com"
[3]: https://raw.githubusercontent.com/artheadsweden/tyr/main/.id-sdlc/intent/pr-draft-20260218-124921/development-plan.md "raw.githubusercontent.com"
[4]: https://raw.githubusercontent.com/artheadsweden/tyr/main/.id-sdlc/zones.yml "raw.githubusercontent.com"
[5]: https://raw.githubusercontent.com/artheadsweden/tyr/main/.github/agents/id-sdlc-intent.agent.md "raw.githubusercontent.com"
[6]: https://code.visualstudio.com/docs/copilot/agents/subagents?utm_source=chatgpt.com "Subagents in Visual Studio Code"
