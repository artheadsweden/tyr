Here’s a concrete, strict roadmap that takes the current Tyr ID-SDLC v0.2 repo state and moves it into something you can adopt incrementally, while also introducing Var as a lightweight profile that shares the same core machinery.

I’m grounding this in how Tyr is currently shaped: the five agent files, deterministic routing via `.id-sdlc/current-intent.json`, zones with `yellow-auto` for new folders, and red-ops as a language-agnostic path and pattern system. ([GitHub][1])

---

## The core decision: Var and Tyr should share one “ID-SDLC Core”

Var shouldn’t be a separate framework. It should be a profile (or mode) that uses the same:

* intent package format
* deterministic routing pointer
* zone model
* red-ops model
* evidence chain format
* validator (static) and optional semantic checks (agent)

So: one `.id-sdlc/` runtime, one validator CLI, and two profiles that decide how many stages you run and how strict the gates are.

Practical consequence: Tyr becomes “full pipeline”, Var becomes “short pipeline”, but both produce the same artifacts and can live in the same repo without forks.

---

## Adoption levels (so strictness is configurable, not philosophical)

Add a setting in `.id-sdlc/governance-config.yml` (or a new `.id-sdlc/profile.yml`) that defines:

* profile: `var | tyr`
* governance_level: `1..4`

Suggested levels:

Level 1 (starter, fail-closed on routing)

* deterministic routing required
* intent package required
* zone enforcement at path level
* evidence-chain produced
* learner optional

Level 2 (strict on scope)

* intent must declare expected zones
* development-plan is required in Tyr, optional in Var
* “new paths” policy enforced (see below)

Level 3 (strict on operations)

* red-ops must be declared as expected vs unexpected
* coding agent must produce an operation report artifact
* validator cross-checks diff vs operation report

Level 4 (strict on knowledge + CI)

* validator is required in CI
* optional semantic red-ops classification step in CI (if org allows LLM in pipeline)
* team/org knowledge packs are read by agents, and learner outputs are publishable (sanitized)

This is how you avoid “too complex”: complexity exists, but you unlock it gradually.

---

## Fixing your two core pain points: yellow-auto and language-agnostic red-ops

### 1) yellow-auto is inherently unsafe unless you gate it

Right now, new folders default to `yellow-auto`. ([GitHub][2])
That’s fine as a staging label, but it becomes dangerous if merges happen without reclassification.

Strict rule to introduce:

* If any `yellow-auto` paths are created, the PR must either:

  * include a human-authored zones update reclassifying them, or
  * explicitly mark the PR as “yellow-auto tolerated” (only allowed at governance_level 1–2), or
  * fail validation (governance_level 3–4)

This turns `yellow-auto` into a governance forcing function instead of a loophole.

### 2) a static validator can’t truly “understand” red-ops across any language

Your current red-ops file is already language-agnostic by design: it relies on path matches and basic patterns. ([GitHub][3])
That’s the right baseline, but it will always be approximate.

So the upgrade is a hybrid:

* deterministic validator (static code) enforces:

  * routing correctness
  * artifact schemas present
  * zone compliance by paths
  * red-ops path triggers (high confidence)
  * cross-check of declared operations vs diff
* coding agent produces an “operation report” artifact:

  * “I changed X, which is operation type Y, here are the files, here are the zones”
  * the validator compares this against the actual diff

This gives you a language-aware classification pass without making the validator a programming-language parser.

---

## Knowledge storage model: personal, team, company

You already have an intelligence folder intended as local-only learner output and gitignored by default. ([GitHub][4])
To support sharing, split knowledge into three distinct categories:

1. Project knowledge (tracked in repo, curated by humans)

* `.id-sdlc/knowledge/`

  * `policies/` (team-specific norms, security rules, release rules)
  * `architecture/` (ADRs, diagrams, invariants)
  * `domain/` (business rules, glossary)
  * `examples/` (golden patterns, “do this not that”)
* This is “static knowledge”, meant to be read by agents.

2. Team intelligence (shareable, derived, sanitized)

* `.id-sdlc/intelligence/team/`

  * `mission-outcomes.ndjson` (sanitized)
  * `friction-zones.json` (aggregated)
* Published by an explicit “publisher” step (human or CI job), not automatically.

3. Company-wide knowledge packs (imported, read-only)

* `.id-sdlc/knowledge-packs/` (git submodule or copied snapshot)
* plus a config list:

  * `.id-sdlc/knowledge-sources.yml`

    * list of sources, precedence, scopes, and “allowed to use in prompts” flags

Manual insertion is then simple:

* humans add notes into `.id-sdlc/knowledge/notes/*.md` with metadata frontmatter
* optional helper CLI scaffolds these notes

---

# Roadmap: v0.5 → v0.6 → v0.7 → …

## v0.5 (foundation release): profiles, validator, operation reporting

Goals

* Var exists as a first-class profile.
* One shared core runtime for Var and Tyr.
* Deterministic validator becomes real static code, not just “agent discipline”.
* Coding produces an operation report artifact to assist validation and review.

Deliverables

1. Profiles

* Add `profile: var|tyr` and `governance_level: 1..4` to governance config.
* Add a new agent: `var-intent-planner.agent.md` that creates:

  * `intent.md`
  * `prompt.md`
  * `development-plan.md` (combined, but still written as separate artifacts)
  * `metadata.json`
* Var reuses existing coding + verification agents unchanged (preferred), or minimal wrappers if you want different naming.

2. Static validator CLI (first version)
   Create a small repo-local CLI, for example:

* `tools/tyr_validate.py` (stdlib-only Python), or a tiny package in `tools/tyr/`

Validator v0.5 checks (fail-closed):

* `.id-sdlc/current-intent.json` schema and folder existence ([GitHub][5])
* required artifacts exist in intent folder (intent/prompt/metadata, plan optional by profile/level)
* diff computation rules (start simple: compare HEAD to parent unless coding_commit_sha is bound)
* zone classification for each changed path using zones.yml ([GitHub][2])
* orange allowlist enforcement (no governance file edits outside allowlist)
* red-ops path triggers (based on `match.paths`) ([GitHub][3])

3. Coding operation report artifact (new)
   Add a required new file written by the coding agent:

* `.id-sdlc/intent/<folder>/operation-report.json`

It includes:

* changed_files (added/modified/deleted)
* created_paths (explicit)
* zones_by_path (what the agent believes each file is)
* red_ops_triggered (list)
* red_ops_suspected (list)
* notes (short)

Why this matters:

* humans can diff “reported vs actual”
* validator can fail if there are changed files not present in the report

Definition of done for v0.5

* You can run Var or Tyr and always get an intent package + evidence trail
* Validator can be run locally and deterministically returns pass/fail with explicit reasons
* Operation-report exists and is cross-checkable

---

## v0.6 (hardening): validator-in-the-loop, attempts log, yellow-auto gates

Goals

* Make “guardrails” an execution loop, not just a review concept.
* Capture failures and retries as first-class evidence the learner can use later.

Deliverables

1. Pre-commit validation loop (agent-driven)
   Update the coding agent workflow to:

* run `tyr validate` before committing
* if validation fails:

  * revert changes (or reset working tree)
  * update the plan with a “failure avoidance note”
  * try again

Important constraint: you still want exactly one final commit. ([GitHub][6])
So store attempts as artifacts without committing intermediate code.

2. Attempts log (new)
   Inside the intent folder:

* `.id-sdlc/intent/<folder>/attempts/attempt-001/validator-report.json`
* `.id-sdlc/intent/<folder>/attempts/attempt-001/failure-notes.md`
* `.id-sdlc/intent/<folder>/attempts/attempt-001/plan-delta.md`

Rule: attempts must never contain code snapshots, only diagnostics and reasoning.

3. yellow-auto gate
   At governance_level 3–4:

* if `.id-sdlc/intent/<folder>/new-paths-yellow-auto.md` exists, validator fails unless:

  * a human has updated zones.yml to classify those paths, or
  * a “temporary tolerance” flag exists in metadata (allowed only at level 1–2)

This directly addresses your concern that new folders can hide anything.

Definition of done for v0.6

* coding can self-correct against the validator without producing multiple commits
* failures become structured evidence instead of lost chat history
* yellow-auto can’t silently slip into production at strict levels

---

## v0.7 (knowledge + learner becomes operational): publishable intelligence, knowledge packs, manual knowledge tooling

Goals

* Learner output stops being “nice but isolated”.
* Teams can share intelligence without sharing raw logs or sensitive content.
* Company-wide policy packs become a real input channel.

Deliverables

1. Team intelligence publishing workflow

* keep local logs as default (as now) ([GitHub][4])
* add a publish step that produces:

  * `.id-sdlc/intelligence/team/friction-zones.json`
  * `.id-sdlc/intelligence/team/mission-outcomes.ndjson` (sanitized)
* add a sanitizer rule set (simple allowlist fields)

2. Knowledge sources config

* `.id-sdlc/knowledge-sources.yml` defining:

  * local repo knowledge folders
  * optional company packs path
  * precedence order
  * “allowed in prompts” toggles

3. Manual knowledge insertion helpers
   Add a CLI or script:

* `tyr knowledge add`

  * creates a new markdown note in `.id-sdlc/knowledge/notes/`
  * enforces frontmatter: tags, scope, owning team, last_reviewed
* `tyr knowledge lint`

  * checks metadata completeness and duplicates

4. Learner reads attempts and validator reports
   Extend learner inputs to include:

* attempt failures and why
* validator failures frequency by zone/red-op
* “friction markers” extracted from these artifacts ([GitHub][7])

Definition of done for v0.7

* a team can share “what we keep tripping on” safely
* a company can ship a knowledge pack that influences every repo without copy-paste
* learner outputs become actionable, not just recorded

---

## v0.8 (CI/CD completion): required validation gates, optional semantic stage, evidence as CI artifact

Goals

* Patrick’s “turn output into knowledge” becomes end-to-end in the pipeline.
* CI enforces deterministic correctness even if humans ignore local guidance.

Deliverables

1. GitHub Actions workflow

* run `tyr validate` on PRs
* upload validator report + evidence-chain as artifacts
* optionally comment a summary on PR

2. Optional semantic red-ops stage (org-permitted)
   If allowed, add a CI step that runs a “semantic classifier” agent over the diff to detect:

* red-ops not caught by path rules
* suspicious auth/security changes outside expected directories

This step must be optional, because many orgs won’t allow LLMs in CI.

3. Evidence-chain enrichment
   Ensure `evidence-chain.json` always references:

* validator version
* validation result hash
* CI run id (when available)

Definition of done for v0.8

* a PR cannot merge without passing deterministic validation at strict levels
* you have an auditable trail even if someone bypasses local practice

---

## v0.9 (governance ergonomics): zone proposals, red-op taxonomy expansion, policy packs versioning

Goals

* make it easier for humans to maintain zones and red-ops without weakening controls.

Deliverables

* `tyr zones propose` produces a patch suggestion for zones.yml (human applies it)
* red-ops taxonomy expands beyond auth/deps/governance into common enterprise hazards (migration, crypto, logging of PII, etc.)
* policy packs gain explicit versioning and compatibility rules

---

## What I would implement first (if you want maximum impact per unit of complexity)

If you do only three things in v0.5, do these:

1. validator CLI (static, deterministic)
2. operation-report.json from the coding agent
3. yellow-auto gating (at higher governance levels)

That triangle closes the biggest loopholes without forcing you to solve “universal language parsing”.

---

If you want, I can turn v0.5 into an implementation-grade spec (folder structure, exact schemas for operation-report and validator output, CLI commands, and the precise changes to each agent prompt), using your current repo conventions and naming.

[1]: https://raw.githubusercontent.com/artheadsweden/tyr/main/.github/agents/id-sdlc-intent.agent.md "raw.githubusercontent.com"
[2]: https://raw.githubusercontent.com/artheadsweden/tyr/main/.id-sdlc/zones.yml "raw.githubusercontent.com"
[3]: https://raw.githubusercontent.com/artheadsweden/tyr/main/.id-sdlc/red_operations.yml "raw.githubusercontent.com"
[4]: https://raw.githubusercontent.com/artheadsweden/tyr/main/.id-sdlc/intelligence/README.md "raw.githubusercontent.com"
[5]: https://raw.githubusercontent.com/artheadsweden/tyr/main/.id-sdlc/current-intent-schema.md "raw.githubusercontent.com"
[6]: https://raw.githubusercontent.com/artheadsweden/tyr/main/.github/agents/id-sdlc-coding.agent.md "raw.githubusercontent.com"
[7]: https://raw.githubusercontent.com/artheadsweden/tyr/main/.github/agents/id-sdlc-learner.agent.md "raw.githubusercontent.com"
