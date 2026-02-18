## Intent Driven Development (IDD)

### Why this matters now

Software development has hit a new asymmetry: implementation can be generated faster than it can be understood.

AI-assisted development increases production capacity dramatically, but human comprehension, review bandwidth, and operational accountability do not scale at the same rate.

When implementation accelerates faster than comprehension:
- reviews become shallow
- specifications drift
- intent becomes implicit
- complexity rises without proportional control

Intent Driven Development (IDD) is a response.

IDD is not a call to slow down. It is a structural shift to keep acceleration bounded and directed.

### The core shift

Traditional development treats **code** as the primary artifact.

IDD inverts that:

- ideas are shaped into explicit **intent**
- intent defines scope, exclusions, boundaries, and verification criteria
- implementation realizes intent
- verification measures alignment with intent

In IDD, code is a realization layer.

Intent is the contract.

### Core principles

1. **Intention precedes implementation**

Every meaningful change begins with a statement of:
- what is to be achieved
- what must not change
- what constraints apply
- how success will be verified

2. **Intent is the contract**

The contract binds:
- the initiator
- the implementer (human or agent)
- the verifier

3. **Boundaries are first-class**

Not all areas of a system carry the same risk. IDD requires explicit boundaries (zones) and explicit handling of high-risk operations (red operations).

4. **Verification is intent-based**

Verification asks: “Does the implementation fulfill the declared intent?”

It is not only about correctness; it is about alignment.

5. **Determinism over assumption**

When uncertainty exists, it must be resolved explicitly. Ambiguity is treated as a risk condition.

### Why this folder exists

`id-sdlc-imp/` is a reference implementation of IDD and ID-SDLC designed to make these principles operational with deterministic agent behavior and auditable artifacts.
