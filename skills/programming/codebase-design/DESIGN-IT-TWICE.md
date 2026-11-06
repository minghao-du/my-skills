# Design It Twice

Use this guide when choosing an important module interface, moving a seam, or consolidating a cluster of modules. The first plausible design is often not the strongest.

This is an optional design exercise, not a mandatory step for every function or small change. Keep the effort proportional to the consequences of the decision.

## 1. Frame the problem

Describe the candidate module and its context:

- The behaviour it should own.
- The callers and their common use cases.
- The constraints every design must satisfy.
- The invariants, ordering rules, error modes, and important operational requirements.
- The dependencies involved and their categories from [DEEPENING.md](DEEPENING.md).
- What should remain hidden behind the seam.
- Any existing domain glossary or terminology the project uses.

If the project has no glossary, use its existing code and documentation as the source of domain terms. Do not assume a `GLOSSARY.md` file exists.

Keep the initial code sketch illustrative. It should clarify constraints, not silently prescribe the answer.

## 2. Produce materially different designs

Create two or three alternatives that differ in a meaningful way. For example:

- **Minimal interface**: few entry points, high leverage, narrow responsibility.
- **Common-case first**: the default caller path is trivial; uncommon options are handled internally or separately.
- **Flexible or policy-oriented**: supports multiple real use cases while keeping policy and mechanism in the right modules.
- **Ports and adapters**: appropriate when external or remote dependencies need a stable seam.

Do not create artificial alternatives that differ only in naming or parameter order.

If sub-agents are available and the design decision justifies the extra time and token cost, ask independent agents to propose alternatives with distinct constraints. Otherwise, generate and critique the alternatives directly. Do not require three or more sub-agents.

Each alternative should state:

1. **Interface**: types, entry points, parameters, defaults, invariants, ordering, and error semantics.
2. **Usage**: a realistic example of how the common caller uses it.
3. **Hidden complexity**: what the module takes responsibility for behind the seam.
4. **Dependencies and adapters**: what is injected, what is internal, and how production and tests use it.
5. **Trade-offs**: where the design provides leverage and locality, and where it adds cost.
6. **Migration impact**: what existing callers and tests would need to change.

## 3. Compare the alternatives

Evaluate each design against the same criteria:

| Criterion | Question |
|---|---|
| Depth and leverage | How much useful behaviour does the caller get per unit of interface it must learn? |
| Interface simplicity | Is the contract small, precise, and easy to use correctly? |
| Common-case simplicity | Is the most frequent use case straightforward, with sensible defaults? |
| Information hiding | Are important design decisions owned in one place, or leaked across callers? |
| Locality | Will related changes and bugs remain concentrated? |
| Layering | Does each layer add a distinct abstraction, or is it pass-through indirection? |
| Error design | Are unnecessary error states eliminated without hiding important failures? |
| Testability | Can behaviour be tested through a stable seam without excessive mocks? |
| Performance | Are relevant costs and critical paths understood? |
| Migration cost | Is the improvement worth the changes required? |

Do not rank designs by line-count ratios, number of classes, or number of methods alone.

## 4. Recommend one design

Give a clear recommendation and explain why it is strongest.

- Prefer the design that makes the overall system simplest, not necessarily the one with the smallest implementation.
- Explain what complexity moves into the module and what knowledge disappears from callers.
- Identify any deliberate trade-off or unresolved risk.
- If a hybrid is better, explain which parts combine cleanly and which should remain separate.
- State when the simpler existing design is already good enough and no refactor is warranted.

The output should help the user make a decision, not leave them with an unranked menu of options.
