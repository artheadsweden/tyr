
## ID-SDLC — Reference Implementation of Intent Driven Development (Tyr)

This repository contains a reference implementation of Intent Driven Development (IDD) and its operational lifecycle model Intent Driven SDLC (ID-SDLC).

It is designed for AI-assisted development environments where implementation throughput can exceed human review bandwidth.

The core idea is simple but structural:
	•	Intent is the contract
	•	Code is a realization of intent
	•	Boundaries are explicit and enforceable
	•	Verification binds intent to a concrete git state
	•	Governance evolves independently from implementation

This repository is not a product.
It is a deterministic development framework.

⸻

### Why ID-SDLC?

AI-assisted development has changed the economics of software production.

We can now generate more code, faster, and across larger scopes than ever before. But human comprehension, review capacity, and architectural oversight have not accelerated at the same rate.

When production outpaces understanding, the system drifts.

ID-SDLC addresses this by making intent explicit and enforceable.

Instead of asking:

What did the code do?

We ask:

What intent was declared, and does the repository state fulfill it?

That inversion is the foundation of the framework.

⸻

### Project Structure

The repository is structured as follows:

.
├── .github/agents/          # VS Code custom agents
├── .id-sdlc/                # Governance and runtime core
├── IDD.md                   # Philosophy of Intent Driven Development
├── ID-SDLC.md               # Lifecycle definition
└── README.md

⸻

### Core Components

1. .id-sdlc/ — Governance and Runtime Core

This folder contains the deterministic control surface of the framework.

It is intentionally separated from application code.

**Key Files**

__zones.yml__
Defines zone classification (green, yellow, red, orange).
Zones determine what agents may modify.

__red_operations.yml__
Defines high-risk operations and allowed agent_action values.
Unknown enforcement values must cause a fail-closed STOP.

__governance-config.yml__
Framework-level configuration.
May define deterministic binding behavior or version markers.

__current-intent.json__
The single routing pointer.
Agents must resolve the active intent folder from this file.
They must never scan for “latest” intent folders.
See `.id-sdlc/current-intent-schema.md` for the required pointer format.

__intent-template.md__
Structural template for new intent packages.

__metadata-schema.md__
Defines required metadata fields for intent binding.

__verification-schema.md__
Defines required structure for verification output.

⸻

### 2. .id-sdlc/intent/ — Intent Packages

Every change begins with an intent package.

Each package lives under:

.id-sdlc/intent/pr-draft-YYYYMMDD-HHMMSS/

An intent package contains:
	•	intent.md — the contract
	•	prompt.md — the executable implementation task
	•	metadata.json — lifecycle metadata
	•	optional: manual-red-changes.md
	•	optional: implementation-summary.md
	•	optional: new-paths-yellow-auto.md
	•	optional: context-ack*.md

The intent package is the single source of truth for a change.

⸻

### 3. .id-sdlc/audit/ — Governance Audit Outputs

Governance audits produce timestamped structured outputs under:

.id-sdlc/audit/YYYYMMDDTHHMMSSZ/

Each audit run contains:
	•	audit.md
	•	audit.json

Audits never modify governance configuration directly.
They only propose improvements.

⸻

### 4. .github/agents/ — Custom Agents

This repository defines role-separated agents:

ID-SDLC Intent

Creates structured intent packages.
Never modifies application code.

ID-SDLC Coding

Implements strictly from intent.
Creates exactly one commit.
Respects zones and red operations.

ID-SDLC Verification

Verifies HEAD against intent.
Binds commit metadata and produces structured verification artifacts.

ID-SDLC Planner

Produces a structured development plan (`development-plan.md`) and aligns `prompt.md` to it.

ID-SDLC Learner

Updates local-only collective intelligence outputs under `.id-sdlc/intelligence/`.

ID-SDLC Governance Auditor

Analyzes governance structure and enforcement logic.
Produces structured audit reports.
Does not modify configuration.

Each agent has strict boundaries and explicit STOP conditions.

⸻

### Lifecycle Overview

The framework defines a deterministic six-stage lifecycle (v0.2):

1. Intent

2. Plan

3. Code

4. Verify

5. Learn

6. Audit

A structured intent package is created under .id-sdlc/intent/.

The routing pointer:

.id-sdlc/current-intent.json

must be updated to reference the new intent folder.

Agents must fail closed if this pointer is missing or invalid.

⸻

## Implementation

The Coding agent:
	•	Reads the active intent package
	•	Enforces zones and red operations
	•	Produces exactly one commit
	•	Writes required artifacts inside the active intent folder

Red zone edits are never performed automatically.
If required, a manual red plan is produced instead.

⸻

### Verification

The Verification agent:
	•	Determines HEAD
	•	Deterministically binds coding_commit_sha
	•	Generates a diff between coding commit and HEAD
	•	Evaluates zone compliance
	•	Evaluates red operation compliance
	•	Evaluates acceptance criteria
	•	Updates metadata
	•	Writes verification.md and verification.json

Verification may produce NOT_READY.
It only STOPs when verification cannot be performed.

⸻

### Audit

The Governance Auditor:
	•	Evaluates governance definitions
	•	Assesses enforcement determinism
	•	Identifies structural weaknesses
	•	Classifies findings by severity
	•	Produces structured audit artifacts

It does not modify governance configuration.

⸻

### Zone Model

Zones define structural risk boundaries:
	•	Green — safe to modify
	•	Yellow — moderate risk
	•	Red — high risk, never auto-modified
	•	Orange — governance runtime surface (.id-sdlc/)

Agents must fail closed on uncertainty.

⸻

### Red Operations

Red operations define high-risk behaviors independent of file location.

Each red operation may specify:
	•	enforcement.treat_as_red
	•	enforcement.agent_action

Allowed agent_action values are defined explicitly in red_operations.yml.

Unknown actions must cause STOP.

No agent may invent enforcement semantics.

⸻

### Determinism Principles

This framework enforces:
	•	No scanning for latest intent
	•	No guessing commit lineage
	•	No ambiguous red-operation interpretation
	•	No silent boundary violations
	•	Explicit STOP protocols
	•	Explicit audit traceability

Fail closed is preferred over silent drift.

⸻

### Relationship Between IDD, ID-SDLC and Tyr

__IDD__
The philosophical foundation.
Intent leads. Code follows.

__ID-SDLC__
The lifecycle model that operationalizes IDD.

__Tyr__
This repository — a concrete, deterministic reference implementation of ID-SDLC.

Tyr stands for “Type Your Rules.”
It demonstrates how to encode intent, enforcement, verification, and governance in a structured, reproducible way.

⸻

What This Repository Is __Not__

	- It is not an application.
	- It is not a CI configuration.
	- It is not a production-ready policy engine.
	- It is not a full compliance framework.

It is a deterministic structural reference.

⸻

### Next Steps

Future evolution may include:

	- CI-based enforcement hooks
	- Toolchain adapters (Copilot, Claude Code, Codex)
	- Schema validation pipelines
	- Governance evolution tracking
	- Versioned framework core separation

⸻

### Closing Thought

Intent Driven Development is not about slowing down AI-assisted coding.

It is about making acceleration bounded, explainable, and structurally safe.

ID-SDLC defines the lifecycle.
Tyr demonstrates how to encode it.

Intent first.
Determinism second.
Code third.

⸻
