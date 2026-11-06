---
name: codebase-design
description: Shared vocabulary and practical principles for designing deep modules, simple interfaces, clear seams, and maintainable code. Use when designing or reviewing module boundaries, improving interfaces, reducing coupling, deepening shallow modules, planning refactors, or making code easier to test and understand.
---

# Codebase Design

Design **deep modules**: put substantial, cohesive behaviour behind an interface that is small and easy for callers to use. Place the interface at a clear **seam** so implementation details and change stay local.

This skill provides a shared design vocabulary and a set of decision principles. It is a **design lens, not a mandatory refactoring procedure**. Apply the smallest subset that helps with the current task; do not turn every code change into an architecture exercise.

The aim is to reduce the complexity of the whole system: less information callers must learn, fewer dependencies they must understand, and fewer places that must change together.

## Glossary

Use these terms consistently when discussing design. They are analytical terms, not a requirement to rename established concepts in the codebase. Preserve precise domain language where it already exists.

**Module**: anything with an interface and an implementation. The term is deliberately scale-agnostic: a function, class, package, process, or tier-spanning slice can be a module.

**Interface**: everything a caller must know to use a module correctly. This includes types and methods, but also invariants, ordering constraints, error semantics, configuration, resource lifecycle, concurrency guarantees, and performance characteristics when callers depend on them. An interface is broader than a language-level `interface` declaration or a method signature.

**Implementation**: the code and decisions hidden inside a module. Callers should not need to understand these details unless they are part of the interface contract.

**Depth**: the leverage a module provides through its interface: how much useful behaviour a caller can access for how much it must learn. A module is **deep** when substantial, cohesive behaviour sits behind a simple interface; it is **shallow** when the interface exposes nearly as much complexity as the implementation hides. Do not measure depth by lines-of-code ratios.

**Seam** (Michael Feathers): a place where behaviour can be varied or replaced without changing the code at the point of use. It is the location of a module's interface and a deliberate design decision.

**Adapter**: a concrete implementation that satisfies an interface at a seam. "Adapter" describes the role it plays; "implementation" describes what it contains.

**Leverage**: what callers gain from depth: more capability per unit of interface they must learn. One well-designed implementation can serve many call sites and tests.

**Locality**: what maintainers gain from depth: related knowledge, changes, bugs, and verification are concentrated in one place rather than spread across callers.

## Deep vs. shallow modules

**Deep module** = a small, understandable interface with substantial implementation behind it.

**Shallow module** = an interface that is almost as complicated as the implementation, or a wrapper that adds little value.

When evaluating depth, ask:

- How much useful work does the module do for each decision its caller must make?
- Can the common use case be expressed simply?
- Does the interface expose internal data, sequencing, configuration, or error handling unnecessarily?
- If this module disappeared, would its complexity disappear, or would it spread across its callers?

A small interface is not automatically good. It must still express the module's real contract clearly and safely. Do not remove meaningful capabilities merely to reduce method count.

## Core design principles

### 1. Hide knowledge, not just code

A module should own a coherent set of design decisions and hide them from callers. Examples include a storage format, protocol details, retry policy, caching strategy, or a domain rule.

Avoid **information leakage**: the same design decision should not need to be understood or reimplemented in several modules.

Avoid **temporal decomposition**: do not split modules merely because operations happen at different times (for example, read → parse → transform → write) when those stages all need to know the same format or rules. Organise around the knowledge that should be local, not only around execution order.

### 2. Make the interface simpler than the implementation

Prefer a small interface that handles substantial work internally. Optimise for the caller's understanding, not for making each implementation function individually simple.

Keep the **common case simple**. Do not force every caller to provide configuration, make policy decisions, or handle rare cases when the module can choose a safe default.

Do not confuse a small interface with a vague interface: document the contract, defaults, invariants, and important failure modes.

### 3. Pull complexity downwards

When a lower-level module can safely own a difficult rule or special case, prefer handling it there instead of making every caller repeat it.

Examples:
- A storage module should own storage-format details.
- A request module should own protocol parsing and validation.
- A scheduler should own the mechanics of retrying or ordering work when that is part of its responsibility.

Do not push complexity down blindly. Keep responsibilities cohesive, preserve important policy choices at the layer that owns them, and avoid creating a giant "god module".

### 4. Give each layer a distinct abstraction

Each layer should provide a useful abstraction for the layer above it.

Watch for:
- **Pass-through methods** that only forward a call without adding policy, translation, validation, or a meaningful abstraction.
- **Pass-through variables** that merely carry information through several layers that do not use it.
- Multiple layers that expose the same concepts and require callers to understand all of them.

A layer is justified when it hides a decision, owns a responsibility, or creates a meaningful change point. Do not add layers just to make the architecture look more modular.

### 5. Choose module boundaries deliberately

Consider combining modules when:
- They share substantial knowledge or invariants.
- Callers must coordinate them to complete one conceptual operation.
- Combining them simplifies the interface or removes meaningful duplication.

Consider keeping modules separate when:
- They represent different concepts or have independent reasons to change.
- One is general-purpose and the other is specific to a particular caller.
- Combining them would create a broad interface, leak unrelated policy, or reduce locality.

Do not split by file size or class count alone. Do not merge unrelated responsibilities just to create a deeper-looking module. See [DEEPENING.md](DEEPENING.md) for dependency-aware guidance.

### 6. Design errors out when it is safe

Ask whether a supposed error case can be made a normal, well-defined outcome. For example, an idempotent delete operation may reasonably treat "already absent" as success.

Do not hide failures that callers genuinely need to know about. Preserve important distinctions such as data loss, authorization failure, unavailable dependencies, or violated invariants. Handle low-level details near their source, and expose only the error information required by callers.

### 7. Design for testability without designing for mocks

Prefer explicit dependencies when they represent genuine variation, an external effect, or a useful seam. Do not create an interface for every class or inject every dependency solely to make tests easy.

Test behaviour through the module's interface where practical. Internal tests can still be useful for complex algorithms or expensive-to-exercise internals, but they should not become a second public contract or make harmless implementation changes difficult.

A seam can be justified by a single production implementation when it isolates a volatile, costly, unsafe, or externally controlled dependency. Multiple adapters are evidence that a seam is useful, not a universal requirement. Avoid speculative seams and mock-heavy tests that duplicate implementation details.

See [DEEPENING.md](DEEPENING.md) for dependency categories and testing strategies.

### 8. Make code obvious to its readers

Prefer precise names, consistent conventions, and familiar structures. A reader should not need to reconstruct hidden assumptions from distant files.

Comments should explain information that is not obvious from the code:
- Interface comments describe what callers can rely on.
- Implementation comments explain non-obvious decisions and why the code is structured that way.
- Comments should not merely paraphrase each line of code.

For important new modules, drafting interface comments before implementation can reveal an awkward abstraction early. Keep comments close to the code they explain and update them when behaviour changes.

### 9. Design important interfaces more than once

The first plausible design is not necessarily the best. For consequential module boundaries or interfaces, compare materially different alternatives before committing.

Do not do this for every small helper. Use [DESIGN-IT-TWICE.md](DESIGN-IT-TWICE.md) when the choice has meaningful long-term consequences or the user asks to explore alternatives.

### 10. Measure performance; optimise the important path

Prefer clear designs and efficient algorithms from the start, but do not optimise based on guesses. Measure real workloads, identify the critical path, and optimise the operations that dominate cost.

Keep common execution paths simple. Avoid spreading low-level performance concerns across callers unless those callers genuinely own the policy.

## Review questions

When designing, changing, or reviewing a module, ask the relevant questions rather than mechanically answering every item:

1. What knowledge or design decision does this module own?
2. What must a caller know to use it correctly? Can any of that knowledge be hidden?
3. Is the common use case simple?
4. Does the module provide meaningful leverage, or is it mostly a pass-through?
5. Are multiple modules sharing knowledge that should have one owner?
6. Does each layer add a distinct abstraction?
7. Are errors and special cases exposed only when callers need them?
8. Is the seam real and useful, or speculative indirection?
9. Can the behaviour be tested through a stable interface?
10. Would another interface design provide better leverage or locality?

## Red flags

Treat these as prompts to investigate, not automatic proof that the design is wrong:

- **Shallow module**: a large or awkward interface hides little behaviour.
- **Information leakage**: multiple modules know the same format, protocol, policy, or invariant.
- **Temporal decomposition**: modules are split by execution step even though they share the same knowledge.
- **Pass-through method or variable**: a layer forwards calls or data without adding a useful abstraction.
- **Overexposure**: callers must understand options, state, or special cases that could be hidden.
- **Special/general mixture**: reusable logic is entangled with one caller's policy.
- **Conjoined modules**: callers must understand and coordinate several modules as if they were one.
- **Repetition**: meaningful logic or knowledge is duplicated across call sites.
- **Vague or hard-to-describe interface**: names and comments cannot state the contract precisely.
- **Non-obvious behaviour**: code surprises readers or relies on undocumented ordering, defaults, or side effects.
- **Change amplification**: one conceptual change requires edits across many unrelated modules.
- **Unknown unknowns**: a maintainer cannot tell what else may need to change.

## Supporting guides

- [DEEPENING.md](DEEPENING.md): deciding whether and how to deepen a cluster, classify dependencies, place seams, and test the result.
- [DESIGN-IT-TWICE.md](DESIGN-IT-TWICE.md): exploring and comparing alternative interfaces for consequential design decisions.
