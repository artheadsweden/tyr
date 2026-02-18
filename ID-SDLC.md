## Intent Driven SDLC (ID-SDLC)

### Introduction

Intent Driven SDLC (ID-SDLC) is an operational lifecycle model built on Intent Driven Development (IDD).

IDD defines the philosophical shift: intent becomes the primary source of truth.

ID-SDLC defines how that shift is executed in a delivery lifecycle where intention, implementation, and verification are deliberately separated.

### Why a new SDLC model is necessary

In AI-assisted environments:
- code production scales quickly
- cross-cutting changes are easier to generate
- review bandwidth stays constant

Without structural controls, the gap between production and comprehension widens.

ID-SDLC closes that gap by:
- making intent explicit
- enforcing boundaries deterministically
- binding verification directly to declared intent

### Lifecycle stages

1. **Intent definition**

Every change begins with an intent artifact describing:
- objective
- scope and exclusions
- constraints and boundaries
- acceptance criteria
- test strategy
- risk notes

Intent is reviewable independently of code.

2. **Controlled implementation**

Implementation occurs strictly within the boundaries declared in intent.

Key rules:
- uncertainty halts execution rather than silently proceeding
- high-risk areas require stronger enforcement

3. **Verification against intent**

Verification measures the implementation against intent:
- scope conformance
- zone compliance
- red-operation compliance
- acceptance criteria alignment

Verification binds intent to a concrete git state.

4. **Audit and refinement**

Over time, governance rules must evolve:
- refine zone boundaries
- improve red-operation detection and enforcement
- identify ambiguity hotspots

Audit is a feedback loop that tightens the model.

### How Tyr implements this

Tyr is the reference implementation inside `id-sdlc-imp/`.

It provides:
- deterministic routing via `id-sdlc-imp/.id-sdlc/current-intent.json`
- explicit zones via `id-sdlc-imp/.id-sdlc/zones.yml`
- explicit red operations via `id-sdlc-imp/.id-sdlc/red_operations.yml`
- agent roles under `id-sdlc-imp/.github/agents/`

### Deterministic routing rule

Agents must never scan for the “latest” intent folder.

They must read the routing pointer (`current-intent.json`) and stop if it is missing, invalid, or points to a non-existent folder.
