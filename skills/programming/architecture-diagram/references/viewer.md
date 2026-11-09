# Viewer build and interaction

From the copied viewer directory run `npm install`, `npm run build`. Deliver `dist/index.html` and a copy of `src/architecture.json`. Dependency downloads are required during build; the built viewer must run offline. Keep the generated package lock. Build uses a single-file Vite bundle and bundled ELK (no worker/CDN/font dependency).

The template provides double-click drill-down, breadcrumbs, local replacement of a module by its children, search that navigates to a matching node's parent, upstream/downstream highlighting, and evidence for nodes and aggregated edges. Cross-boundary endpoints appear as external cards. Edge aggregation preserves the underlying relationship list.

Use a light canvas, responsibility-colored cards, restrained borders, orthogonal edges and readable spacing. Keep summaries short; put detail in the inspector. Increase decomposition when a level becomes too dense. Inspect actual rendered layouts; automatic placement alone is not visual verification.

Official implementation references (consult when adapting APIs):
- https://reactflow.dev/learn/customization/custom-nodes
- https://reactflow.dev/learn/layouting/sub-flows
- https://reactflow.dev/learn/layouting/layouting
- https://github.com/kieler/elkjs

Mermaid can be an optional documentation export; it is not a replacement for the interactive HTML. Cytoscape.js is an alternative for graph-analysis-heavy requests, requiring equivalent navigation and offline verification.
