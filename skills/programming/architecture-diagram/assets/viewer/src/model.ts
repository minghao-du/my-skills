export type Evidence = { status: 'observed' | 'proposed' | 'inferred'; source: string; detail: string };
export type Component = { id: string; parent?: string; label: string; summary: string; kind: 'service' | 'store' | 'external' | 'interface'; evidence: Evidence[] };
export type Relation = { id: string; source: string; target: string; label: string; evidence: Evidence[] };
export type Architecture = { title: string; revision: string; views: { id: string; label: string; notes: string[]; nodes: Component[]; edges: Relation[] }[] };
export function validate(model: Architecture) {
  if (!model.views.length) throw new Error('At least one view is required');
  for (const view of model.views) {
    const ids = new Set(view.nodes.map(n => n.id));
    if (ids.size !== view.nodes.length) throw new Error('Duplicate node IDs');
    const edgeIds = new Set(view.edges.map(e => e.id));
    if (edgeIds.size !== view.edges.length) throw new Error('Duplicate edge IDs');
    for (const n of view.nodes) {
      const seen = new Set([n.id]); let parent = n.parent;
      while (parent) {
        if (!ids.has(parent) || seen.has(parent)) throw new Error('Invalid hierarchy: ' + n.id);
        seen.add(parent); parent = view.nodes.find(x => x.id === parent)!.parent;
      }
    }
    for (const e of view.edges) if (!ids.has(e.source) || !ids.has(e.target)) throw new Error('Unknown edge endpoint');
    for (const item of [...view.nodes, ...view.edges]) if (!item.evidence?.length || item.evidence.some(e => !['observed','proposed','inferred'].includes(e.status) || !e.source || !e.detail)) throw new Error('Missing evidence: ' + item.id);
  }
}
