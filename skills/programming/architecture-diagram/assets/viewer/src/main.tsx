import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ReactFlow, ReactFlowProvider, Controls, Background, Handle, Position, useReactFlow, applyNodeChanges, type Node, type Edge, type NodeProps } from '@xyflow/react';
import ELK from 'elkjs/lib/elk.bundled.js';
import raw from './architecture.json';
import { validate, type Architecture, type Evidence } from './model';
import '@xyflow/react/dist/style.css';
import './style.css';
const model = raw as Architecture;
const elk = new ELK();
function Card({data}: NodeProps) {
  return <div className={'card '+data.kind} style={{opacity:data.dim ? .25 : 1}}><Handle type="target" position={Position.Left}/><small>{data.external ? '外部边界' : String(data.kind)}</small><strong>{String(data.label)}</strong><p>{String(data.summary)}</p>{Boolean(data.children) && <button className="nodrag" onClick={e=>{e.stopPropagation(); (data.expand as ()=>void)();}}>展开子模块</button>}<Handle type="source" position={Position.Right}/></div>;
}
const nodeTypes = { card: Card };
function EvidenceList({items}: {items:Evidence[]}) {return <>{items.map((e,i)=><section key={i}><b>{({observed:'代码已证实',proposed:'方案设计',inferred:'推断'})[e.status]}</b><pre>{e.source}</pre><p>{e.detail}</p></section>)}</>}
function App() {
 const [vi,setVi]=useState(0), [scope,setScope]=useState<string|undefined>(), [expanded,setExpanded]=useState<string[]>([]), [query,setQuery]=useState(''), [selected,setSelected]=useState<string>(), [edgeSelection,setEdgeSelection]=useState<string[]>([]), [direction,setDirection]=useState('all'), [nodes,setNodes]=useState<Node[]>([]), [edges,setEdges]=useState<Edge[]>([]), [error,setError]=useState('');
 const flow=useReactFlow(); const view=model.views[vi];
 const enter=(id?:string)=>{setScope(id);setExpanded([]);setSelected(undefined);setEdgeSelection([])};
 const ancestors: string[]=[]; let cursor=scope; while(cursor){ancestors.unshift(cursor);cursor=view.nodes.find(n=>n.id===cursor)?.parent;}
 useEffect(()=>{
  let cancelled=false;
  const visible=new Set<string>();
  const add=(parent?:string)=>view.nodes.filter(n=>n.parent===parent).forEach(n=>expanded.includes(n.id)?add(n.id):visible.add(n.id)); add(scope);
  const representative=(id:string):string|undefined=>{let n=view.nodes.find(n=>n.id===id);while(n){if(visible.has(n.id))return n.id;n=view.nodes.find(x=>x.id===n!.parent);}return undefined;};
  const groups=new Map<string,{source:string;target:string;ids:string[];labels:string[]}>(); const boundary=new Set<string>();
  for(const e of view.edges){let s=representative(e.source),t=representative(e.target);if(!s&&!t)continue;if(s===t)continue;if(!s){s=e.source;boundary.add(s)}if(!t){t=e.target;boundary.add(t)}const key=JSON.stringify([s,t]);const group=groups.get(key)||{source:s,target:t,ids:[],labels:[]};group.ids.push(e.id);group.labels.push(e.label);groups.set(key,group);}
  const relevant=new Set<string>(); if(selected){relevant.add(selected); for(const n of view.nodes){let p=n.parent;while(p){if(p===selected){relevant.add(n.id);break}p=view.nodes.find(x=>x.id===p)?.parent;}}let changed=true;while(changed){changed=false;for(const e of view.edges){const from=direction==='up'?e.target:e.source,to=direction==='up'?e.source:e.target;if(relevant.has(from)&&!relevant.has(to)){relevant.add(to);changed=true}}}}
  const shown=[...visible,...boundary].map(id=>view.nodes.find(n=>n.id===id)!);
  const graphEdges=[...groups].map(([id,g])=>({id,source:g.source,target:g.target,label:[...new Set(g.labels)].join(' · '),type:'smoothstep',data:{ids:g.ids},style:{stroke:'#64748b'},markerEnd:{type:'arrowclosed' as const}}));
  const graphNodes=shown.map(n=>({id:n.id,type:'card',position:{x:0,y:0},data:{...n,external:boundary.has(n.id),children:!boundary.has(n.id)&&view.nodes.some(c=>c.parent===n.id),expand:()=>setExpanded(xs=>[...xs,n.id]),dim:direction!=='all'&&selected&&![...relevant].some(id=>id===n.id||representative(id)===n.id)}}));
  elk.layout({id:'root',layoutOptions:{'elk.algorithm':'layered','elk.direction':'RIGHT','elk.spacing.nodeNode':'55','elk.layered.spacing.nodeNodeBetweenLayers':'120'},children:shown.map(n=>({id:n.id,width:240,height:170})),edges:graphEdges.map(e=>({id:e.id,sources:[e.source],targets:[e.target]}))}).then(layout=>{if(cancelled)return;setNodes(graphNodes.map(n=>({...n,position:{x:layout.children!.find(c=>c.id===n.id)!.x!,y:layout.children!.find(c=>c.id===n.id)!.y!}})));setEdges(graphEdges);requestAnimationFrame(()=>flow.fitView({padding:.2}));}).catch(e=>!cancelled&&setError(String(e)));
  return ()=>{cancelled=true};
 },[vi,scope,expanded,selected,direction]);
 const detail=view.nodes.find(n=>n.id===selected);
 return <><header><div><h1>{model.title}</h1><small>{model.revision}</small></div><select aria-label="架构视图" value={vi} onChange={e=>{setVi(Number(e.target.value));enter()}}>{model.views.map((v,i)=><option value={i} key={v.id}>{v.label}</option>)}</select><input aria-label="搜索模块" placeholder="搜索所有层级…" value={query} onChange={e=>setQuery(e.target.value)}/></header>{query&&<div className="results">{view.nodes.filter(n=>(n.label+' '+n.summary).toLowerCase().includes(query.toLowerCase())).map(n=><button key={n.id} onClick={()=>{enter(n.parent);setSelected(n.id);setQuery('')}}>{n.label}</button>)}</div>}<nav><button onClick={()=>enter()}>总览</button>{ancestors.map(id=><button key={id} onClick={()=>enter(id)}> / {view.nodes.find(n=>n.id===id)!.label}</button>)}<button onClick={()=>{setExpanded([]);setDirection('all');flow.fitView()}}>收起 / 重置</button></nav><main><div className="canvas">{error&&<p role="alert">{error}</p>}{!nodes.length&&<p className="empty">当前层级没有模块</p>}<ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodesChange={changes=>setNodes(ns=>applyNodeChanges(changes,ns))} onNodeClick={(_,n)=>{setSelected(n.id);setEdgeSelection([])}} onNodeDoubleClick={(_,n)=>{if(view.nodes.some(c=>c.parent===n.id))enter(n.id)}} onEdgeClick={(_,e)=>{setSelected(undefined);setEdgeSelection(e.data!.ids as string[])}} fitView><Controls/><Background gap={24}/></ReactFlow></div><aside><h2>{detail?.label||'架构说明'}</h2>{detail?<><p>{detail.summary}</p><div className="actions"><button onClick={()=>setDirection('up')}>上游</button><button onClick={()=>setDirection('down')}>下游</button><button onClick={()=>setDirection('all')}>全部</button>{view.nodes.some(n=>n.parent===detail.id)&&<button onClick={()=>enter(detail.id)}>进入模块</button>}</div><EvidenceList items={detail.evidence}/></>:edgeSelection.length?view.edges.filter(e=>edgeSelection.includes(e.id)).map(e=><section key={e.id}><h3>{e.label}</h3><p>{e.source} → {e.target}</p><EvidenceList items={e.evidence}/></section>):<><p>双击进入模块，点击查看来源。连线箭头表示关系方向。</p>{view.notes.map((n,i)=><p key={i}>{n}</p>)}</>}</aside></main></>;
}
try{validate(model);createRoot(document.getElementById('root')!).render(<ReactFlowProvider><App/></ReactFlowProvider>)}catch(e){document.getElementById('root')!.textContent='模型错误：'+String(e)}
