# Design It Twice

Use this guide for **Branch C** when choosing a consequential module decomposition, moving a seam, or designing an important exposed interface. Keep the scope strictly at module boundaries, submodule structure, and exposed contracts.

## 1. Frame the Boundary Problem

Capture the architectural constraints before proposing alternatives:

- Owned behaviour and hidden design decisions.
- Primary callers, frequent use cases, and critical paths.
- Essential guarantees callers depend on (avoiding false abstractions), invariants, ordering/concurrency rules, and error conditions.
- Cross-module decisions and external/volatile dependencies requiring a `Seam`.
- Domain terminology drawn from existing codebase concepts.

Keep any initial sketch illustrative so it clarifies constraints without locking in the first structure.

## 2. Sketch 2–3 Materially Different Designs

Generate two or three alternatives that differ in structure, responsibility placement, or abstraction—varying parameter order or naming alone counts as one design. Examples of distinct directions:

- **Minimal general-purpose interface**: Few entry points, high leverage, caller-agnostic primitives.
- **Common-case-first layered split**: Trivial default path at the outer boundary, specialized options or policies isolated in a distinct submodule or layer.
- **Seam-isolated core**: Domain module decoupled from volatile or external dependencies via focused internal or public `Seam` / `Adapter` boundaries.

Document each alternative with this lightweight comparison skeleton:

1. **Module & submodule tree**: Breakdown and where complexity sits.
2. **Exposed interface sketch**: Key entry points, common-case caller path, essential guarantees, and error/special-case strategy.
3. **Hidden complexity & seams**: Decisions absorbed inward, `Seam` boundaries, and `Context` usage.
4. **Trade-offs & ripple scope**: Gains in depth/locality versus coupling or migration surface across peer modules.

## 3. Compare Against Architectural Criteria

Evaluate every alternative on the same table (judging depth by caller cognitive load rather than line or class counts):

| Criterion | Architectural Question |
|---|---|
| Depth & leverage | How much capability does the caller gain per unit of interface it must learn? |
| General-purpose clarity | Does the exposed contract serve current needs without leaking one caller's policy? |
| Common-case & critical-path simplicity | Is the frequent/hot path concise with safe defaults and minimal cross-layer hops? |
| Information hiding & false-abstraction safety | Are internal decisions hidden while caller-essential guarantees remain explicit? |
| Layer distinctness | Does each module/layer add a distinct abstraction without pass-throughs or decorator bloat? |
| Error & special-case design | Are unnecessary errors/special cases defined out, masked, or aggregated cleanly? |
| Ripple scope | Are related changes concentrated locally, and is migration cost justified? |

## 4. Recommend One Design

Deliver a single decisive recommendation rather than an unranked menu:

- Identify the winning design (or a clean hybrid with explicit boundary seams) and explain what complexity moves inward and what cognitive load disappears from callers.
- Name the deliberate trade-offs and remaining architectural risks.
- Confirm when an existing module boundary is already sufficiently deep and requires no structural change.

Complete when all 2–3 alternatives are evaluated on the full criteria table, one design is decisively recommended, and the recommended design is documented with all four **Completion Criteria** sections from [SKILL.md](SKILL.md).
