---
name: codebase-design
description: "Deep modules: use when decomposing a system into modules and submodules, designing or simplifying a module's exposed interface, reviewing coupling to deepen or split boundaries, or comparing alternative boundary architectures."
---

# Codebase Design

Design **deep modules**: concentrate substantial, cohesive behaviour and design decisions behind a simple, general-purpose **interface**. Deliver an architectural specification—module trees, submodule boundaries, exposed interface contracts, and dependency seams—keeping output at the architectural design level rather than writing implementation code, tests, or diagram scripts.

## Workflows

Select the branch matching the task. Present architectures via structured text/ASCII trees and interface contracts.

### Branch A: Greenfield Module & Interface Design

1. **Frame scope and shared decisions**: Identify core capabilities, primary callers, critical paths, invariants, external/volatile dependencies, and cross-module decisions. Done when all callers, external dependencies, and shared decisions in scope are accounted for.
2. **Partition modules and submodules**: Group responsibilities around hidden knowledge and independent change axes (Principles 1–5); decide for each module whether it stays unified or splits into internal submodules, quarantining unavoidable complexity inside rarely touched internal submodules. Done when every responsibility and cross-module decision has a single owner or canonical spec.
3. **Specify exposed interfaces and seams**: Draft each module's public contract first (Principles 6–11)—formal/informal surface, defaults, error/special-case strategy, `Seam` boundaries, and `Context` ownership. Done when every contract is complete without internal mechanics.
4. **Verify**: Satisfy **Completion Criteria** for every module in scope.

### Branch B: Boundary Review & Deepening

1. **Map current boundaries**: Trace existing modules, submodule splits, exposed contracts, critical paths, and cross-module dependencies; tag symptoms using the **Red Flags** table. Done when every module and boundary in scope is mapped and tagged.
2. **Restructure boundaries**: Apply Principles 1–5 to merge shallow or conjoined modules, collapse pass-throughs or decorator chains, and separate general-purpose mechanism from caller-specific policy. Done when every tagged boundary has an explicit merge, split, or keep decision.
3. **Simplify exposed contracts and seams**: Replace pass-through state with `Context`, generalize caller-coupled APIs, apply the 4-way error/special-case toolkit, and verify `Seam` purity (Principles 6–11). Done when every modified interface satisfies contract-first clarity.
4. **Verify**: Satisfy **Completion Criteria** for every module in scope.

### Branch C: Consequential Boundary Comparison

When a major module split, seam placement, or exposed interface carries high long-term impact and admits genuinely different structures, read and execute [DESIGN-IT-TWICE.md](DESIGN-IT-TWICE.md) to compare 2–3 materially different designs, deliver one clear recommendation, and satisfy **Completion Criteria** for the recommended design.

## Completion Criteria

A task completes only when **every module in scope** has all four sections explicitly documented in the architectural specification:

1. **Module & Submodule Tree**: Responsibility, hidden design decisions, internal submodule breakdown (or rationale for remaining unified), and textual hierarchy map.
2. **Exposed Interface Contract**: Public entry points/types, minimal caller mental model, common-case defaults, critical-path behaviour, invariants/ordering/concurrency guarantees, and error/special-case disposition (defined out, masked, aggregated, fail-fast, or exposed).
3. **Dependency & Seam Map**: Dependency directions, single owner or canonical spec for cross-module decisions, `Seam` / `Adapter` boundaries for external/volatile dependencies, and `Context` ownership.
4. **Red-Flag Audit**: Verification that every row in the **Red Flags** table was checked across all modules in scope, with every flag resolved or justified and public contracts containing only caller-visible semantics.

## Vocabulary

- **Module**: any architectural unit with an interface and hidden internals (package, service, subsystem, class, or component).
- **Interface**: everything a caller must know to use a module—formal signatures/types plus informal semantics (defaults, invariants, ordering constraints, concurrency guarantees, side effects, critical-path guarantees, and error behaviour).
- **Depth**: capability gained by callers per unit of cognitive load required by the interface. A **deep module** offers high leverage behind a small contract; a **shallow module** exposes nearly as much complexity as it hides.
- **False abstraction**: an interface that looks simple by omitting details callers genuinely need, creating obscurity and unknown unknowns.
- **Seam**: a deliberate boundary where an implementation can be replaced without changing callers, isolating external, volatile, or costly dependencies behind an **Adapter**.
- **Context**: an instance-scoped object holding configuration and shared runtime state, replacing process-wide globals and pass-through parameters.

## Architectural Principles

### Module and Submodule Boundaries

1. **Hide knowledge, not execution steps**: Organise modules and submodules around cohesive design decisions (storage format, protocol, domain rule, scheduling policy) rather than runtime order. Quarantine unavoidable complexity inside rarely touched internal submodules.
2. **Merge vs. split by coupling and generality**:
   - **Bring together** when submodules share hidden knowledge/invariants, are bidirectionally co-used, overlap conceptually, cannot be understood independently, or combine to simplify the public interface.
   - **Keep apart** when a dependency is unidirectional (e.g., domain cache using a generic hash table), responsibilities represent independent change axes, or general-purpose mechanism is mixed with caller-specific policy. Avoid **Classitis** (splitting by arbitrary size or step count) and shallow **Decorator/Wrapper** layers (fold common features into the base module or separate independent ones).
   - **Prefer composition and interface inheritance**: Express shared behaviour via composition or one deep interface with multiple implementations rather than implementation inheritance that leaks state across parent/child boundaries.
3. **Give each layer a distinct abstraction**: Every architectural layer translates concepts rather than forwarding calls or carrying pass-through parameters down the stack. Consolidate layers whose abstractions mirror each other, and keep critical paths free of redundant cross-layer hops and repeated state checks.
4. **Own cross-module decisions once**: Encapsulate each format, protocol, or invariant inside one owning module. When a decision inevitably spans peer modules (e.g., wire protocol, shared status enum, distributed coordination), establish **one canonical specification anchor** (shared schema or central design note) rather than duplicating rules across modules.
5. **Pull cohesive complexity downward**: Absorb awkward mechanics, defaults, and bookkeeping inside lower-level modules or internal submodules whenever doing so is cohesive with the module and simplifies callers' interfaces.

### Exposed Interface Design

6. **Make exposed interfaces somewhat general-purpose**: Build internals for current needs, while shaping the public interface around general concepts rather than one caller's specific workflow or UI actions. General-purpose surfaces stay smaller, hide caller policy, and eliminate shallow one-off methods.
7. **Optimise for the common case and critical path**: Provide safe defaults so frequent caller paths require minimal setup; isolate rare options behind separate paths or optional configuration, and design interfaces so critical paths avoid chattiness or extra round-trips.
8. **Specify the interface contract first — without false abstractions**: Draft the module's public contract (responsibilities, preconditions, side effects, invariants, defaults, concurrency, error semantics) before designing internal submodules. Use difficulty describing a contract concisely as an early signal to redraw boundaries. Expose every guarantee or parameter callers genuinely depend on (e.g., durability/flushing rules, critical failures, workload-dependent tuning), while keeping internal mechanics out of interface specifications.
9. **Design errors and special cases at the boundary**: Choose deliberately across four mechanisms, exposing an error only when callers must act on it (never mask failures callers need to observe):
   - **Define out of existence**: Adjust semantics or model empty states normally (e.g., an empty range instead of a nullable selection flag; idempotent deletion) so error branches disappear.
   - **Mask downward**: Handle transient or low-level conditions (retries, transport hiccups) inside the module when callers cannot act usefully on them.
   - **Aggregate upward**: Route uniform failure classes to one higher-level boundary handler instead of scattering handlers across submodules.
   - **Fail fast**: Abort cleanly with diagnostic context on unrecoverable bugs or broken invariants.

### Dependency Seams and Architectural Testability

10. **Place seams only at real variation points**: Introduce a `Seam` to isolate true external dependencies (third-party vendors, remote services, hardware, volatile protocols) or real production variants. Keep internal seams private to the module rather than widening the public interface.
11. **Shape boundaries for clean verification**:
    - Design each module's complete abstraction holistically rather than letting feature-by-feature test pressure fragment the interface into tactical methods.
    - Encapsulate module-wide state in an explicit `Context` instance so multiple independent instances can coexist in one process.
    - Verify seam purity by confirming the interface supports both production and lightweight stand-in implementations without leaking implementation details.

## Red Flags

| Symptom | Architectural Cause | Corrective Move |
|---|---|---|
| **Shallow module / Classitis** | Interface nearly as complex as internals, or tiny modules split by size/step | Deepen by pulling cohesive work inward or merging co-dependent modules |
| **False abstraction** | Interface looks simple by omitting guarantees or parameters callers need | Expose the essential guarantee, tuning knob, or failure explicitly in the contract |
| **Information leakage** | Same format, rule, or invariant embedded in multiple modules | Consolidate behind one owning module or one canonical cross-module spec |
| **Temporal decomposition** | Modules/submodules split by execution order (read → parse → write) | Regroup around shared knowledge and data ownership |
| **Conjoined modules** | Submodules or peers cannot be understood or changed independently | Merge into one module or redraw the boundary along hidden knowledge |
| **Pass-through / Decorator bloat** | Layer forwards calls, carries unused parameters, or thinly wraps a base API | Collapse the layer, fold common behaviour into the base, or move state into `Context` |
| **Overexposure / Special-general mixture** | Public API forces rare options or mixes reusable core with one caller's policy | Generalize the public contract, provide defaults, isolate caller policy above |
| **Implementation inheritance coupling** | Parent/child modules share mutable state or override-coupled internals | Replace with composition or interface inheritance over one deep contract |
| **Vague / Hard-to-describe contract** | Interface requires long caveats or internal mechanics to explain | Redraw module boundaries until the abstraction is crisp and self-contained |
| **Change amplification / Unknown unknowns** | One conceptual change edits distant modules or hides implicit couplings | Eliminate duplication and anchor remaining cross-module rules at one explicit seam/spec |
