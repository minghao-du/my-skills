# Deepening a Cluster of Modules

Use this guide when several shallow or tightly coupled modules appear to form one conceptual responsibility. The goal is to improve the system's overall design, not simply to merge files or reduce module count.

This guide uses the vocabulary from [SKILL.md](SKILL.md): **module**, **interface**, **depth**, **seam**, and **adapter**.

## 1. Decide whether the modules belong together

Before looking at dependency mechanics, understand the responsibilities and knowledge involved.

Deepening is a candidate when:
- Multiple modules share the same rules, format, protocol, or invariants.
- Callers must understand and coordinate several modules to perform one conceptual operation.
- A change to one concept routinely requires edits in several places.
- A simpler interface could hide the coordination and knowledge from callers.

Keep modules separate when they represent different concepts, have independent reasons to change, or when combining them would mix general-purpose behaviour with caller-specific policy.

**Dependency category does not decide whether modules should be merged.** It informs how a chosen design should isolate and test its dependencies.

## 2. Classify dependencies to choose a testing strategy

### A. In-process

Examples: pure computation, in-memory state, local libraries.

- These dependencies may be combined without a runtime adapter when they share a coherent responsibility.
- Test the resulting behaviour through the deepened module's interface when practical.
- Keep a separate module if it represents a useful independent concept, is reused independently, or has a different reason to change.

Do not merge pure functions automatically; purity makes composition easier, not necessarily better.

### B. Local-substitutable

Examples: a local database such as PGLite, an in-memory filesystem, or another realistic test implementation.

- Use the stand-in when it exercises the relevant behaviour more faithfully than a large collection of mocks.
- A public port is not automatically necessary. If substitution is private to the module's tests, keep the seam internal.
- Add a public seam only when callers or production composition genuinely need to select an implementation.

### C. Remote but owned

Examples: your own service reached through HTTP, gRPC, or a queue.

- Decide whether the deep module should own domain behaviour while transport details sit behind an adapter.
- Introduce a port when it hides transport mechanics, isolates a volatile dependency, or supports a real alternative.
- Test domain behaviour with an in-memory adapter where useful.
- Keep at least one integration or contract test for the real transport so the in-memory adapter does not drift from production behaviour.

### D. True external

Examples: Stripe, Twilio, or a third-party service you do not control.

- Keep vendor-specific request, response, authentication, and retry details behind a focused adapter.
- Prefer a small, stable seam around the external capability actually used.
- Use fakes or mocks for deterministic unit tests where appropriate, but avoid tests that reproduce vendor internals or assert on private call sequences.
- Use a sandbox or integration test when it provides meaningful confidence and is safe to run.

## 3. Place seams deliberately

A seam is useful when it isolates a real source of variation, change, risk, cost, or external effect.

Good reasons include:
- A dependency is outside the module's control.
- Production and test environments need different implementations.
- A volatile protocol or vendor API should not leak into domain logic.
- A resource is expensive, unsafe, or nondeterministic to use in ordinary tests.

Avoid introducing a seam only because "we might need another implementation someday".

The presence of two adapters (for example, production and test) is evidence that a seam is useful, but it is not a rule. A single production adapter can still justify a seam when it isolates a volatile or externally controlled dependency. Conversely, a mock created only to satisfy a test does not automatically justify a new public interface.

Keep internal seams internal. Do not expose implementation details through the module's external interface merely because its own tests need to replace a dependency.

## 4. Test the new design

Prefer tests that describe observable behaviour through the deepened module's interface.

1. Identify the behaviours currently covered by tests for the shallow modules.
2. Add tests for those behaviours at the new interface, including important invariants and failure modes.
3. Add integration or contract tests for real external adapters when needed.
4. Keep focused internal tests when they provide meaningful coverage of complex algorithms or difficult edge cases.
5. Delete old tests only when their coverage is genuinely redundant with the new tests.

Do not mechanically delete every lower-level test. The goal is to remove duplicated or brittle tests, not to lose useful confidence.

Tests should generally survive internal refactoring. If a test breaks whenever private implementation details change, consider whether it is testing at the wrong level.

## 5. Check the result

After deepening, verify:

- Callers need to know fewer internal details.
- The common use case is simpler.
- Related knowledge and changes are more local.
- The new interface states its invariants, errors, and important operational constraints.
- Each remaining module has a distinct responsibility and abstraction.
- The design did not create a giant module or move unrelated policy into one place.
- Tests cover behaviour at the appropriate seam without depending excessively on implementation details.

A successful deepening reduces the total complexity across the module and its callers. A larger implementation is acceptable when it creates a substantially simpler system.
