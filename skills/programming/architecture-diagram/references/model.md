# Architecture data contract

The executable types in `assets/viewer/src/model.ts` are authoritative for field names. The bundled sample illustrates a proposed architecture, not extracted repository evidence.

Each view contains a rooted forest of nodes and directed edges. Omit `parent` for top-level nodes. IDs must be unique within a view; parents and endpoints must exist, and parent chains must terminate. Empty views are allowed and display an empty state.

Every node and edge has nonempty evidence: `observed` (inspected code), `proposed` (written design), or `inferred` (explicit reasoning). Sources are plain text with a path/symbol/section and explanatory detail; the viewer treats them as text, never executable HTML. Use `notes` for scope omissions and unresolved contradictions.

Use stable semantic IDs across regeneration. Each edge describes one relationship with a verb label. Parent-level aggregation is a display operation: the model retains original endpoints and evidence. Files and functions usually belong in evidence; promote them to nodes only when needed for the question.
