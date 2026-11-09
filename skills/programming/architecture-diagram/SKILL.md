---
name: architecture-diagram
description: Architecture diagrams from repository code or written designs. Use when the user wants to understand a software system through an interactive, layered architecture map or regenerate one after changes.
---

# Architecture diagram

Build an evidence-backed architecture explorer: overview first, then drill into responsibilities and relationships. Deliver an offline HTML file and its editable architecture JSON.

## 1. Establish the map

Use the user's scope and language. Default to system → subsystem → component, adapting levels to actual boundaries. Record the input revision/date and examined scope. For repository inputs, read [repository.md](references/repository.md); for written designs, read [design.md](references/design.md). Use both for mixed inputs.

Complete when entry points, major responsibilities, storage and external systems within scope are accounted for, with omissions explicitly recorded. Resolve only material ambiguities with the user; choose presentation details yourself.

## 2. Model the evidence

Read [model.md](references/model.md) and produce `architecture.json`. Assign stable IDs and meaningful responsibility summaries. Every node and edge carries its own evidence status and source. Keep proposed and implemented architectures in separate views when they differ. Preserve uncertain relationships as labeled inference.

Complete when parents form an acyclic hierarchy, all edge endpoints exist, every item has evidence, and the major user journey can be followed through the graph. A file import proves a static dependency; runtime calls need separate evidence.

## 3. Build the explorer

Copy `assets/viewer/` into the output workspace; replace `src/architecture.json` with the model. Follow [viewer.md](references/viewer.md) for build and interaction behavior. The template uses TypeScript, React Flow and ELK. Adapt labels and appearance to the user's language while retaining navigation, source inspection and offline packaging.

Complete when `npm run build` produces `dist/index.html`, all runtime resources are embedded, and the JSON remains available alongside it. Keep the generated lockfile with the build sources for repeatable rebuilds.

## 4. Verify and deliver

Open the built file via `file://` in an available browser with network disabled. Exercise drill-down and breadcrumb return, local expand/collapse, search across levels, upstream/downstream highlighting, node and edge evidence, pan/zoom and reset. Inspect overview and deepest populated level for cropped labels, overlapping cards and unreadable edges. Check console errors and unexpected network requests. Repair observed issues and recheck affected paths.

Compare displayed relationships with original evidence, including at least one cross-boundary relationship. Record unverified interactions honestly when browser tooling is unavailable.

Deliver links to the HTML and JSON, the source revision/scope, and material uncertainties. Completion requires both usable artifacts and a truthful verification result; a development server alone is not the deliverable.
