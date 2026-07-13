from __future__ import annotations


def render_dashboard(project: str | None = None) -> str:
    proj = project or ""
    return (
        """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>pneural-context Dashboard</title>
<style>
:root{--bg:#0a0e1a;--surface:#111827;--border:#1e293b;--border-hover:#334155;--accent:#06b6d4;--accent2:#8b5cf6;--success:#10b981;--warning:#f59e0b;--error:#ef4444;--text:#e2e8f0;--text2:#94a3b8;--text3:#64748b;--mono:'JetBrains Mono','Fira Code',monospace;--radius:10px}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{font-family:Inter,system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--text);font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased}
.topbar{display:flex;align-items:center;gap:16px;padding:12px 24px;background:var(--surface);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:10}
.topbar h1{font-size:18px;font-weight:700;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.topbar .ver{font-size:11px;color:var(--text3);margin-left:8px}
.topbar .spacer{flex:1}
.topbar select,.topbar input,.topbar button{font-family:inherit;font-size:13px;border:1px solid var(--border);border-radius:6px;padding:6px 12px;background:var(--bg);color:var(--text);outline:none;transition:border-color .2s}
.topbar select:focus,.topbar input:focus{border-color:var(--accent)}
.topbar button{background:var(--accent);color:#000;border:none;font-weight:600;cursor:pointer;transition:opacity .2s}
.topbar button:hover{opacity:.85}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px;padding:20px 24px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:16px;transition:border-color .2s}
.card:hover{border-color:var(--border-hover)}
.card h2{font-size:11px;text-transform:uppercase;letter-spacing:1.2px;color:var(--text3);margin-bottom:10px;display:flex;align-items:center;gap:6px}
.card h2 .icon{font-size:14px}
.big-num{font-size:32px;font-weight:700;line-height:1.1}
.sub{font-size:12px;color:var(--text3);margin-top:4px}
.list{margin-top:10px}
.list li{padding:6px 0;border-bottom:1px solid var(--border);font-size:13px;display:flex;align-items:center;gap:8px}
.list li:last-child{border-bottom:none}
.badge{display:inline-block;padding:1px 7px;border-radius:4px;font-size:10px;font-weight:700;letter-spacing:.3px}
.badge-critical{background:rgba(239,68,68,.15);color:var(--error)}
.badge-important{background:rgba(245,158,11,.15);color:var(--warning)}
.badge-normal{background:rgba(100,116,139,.15);color:var(--text3)}
.badge-concept{background:rgba(6,182,212,.15);color:var(--accent)}
.badge-procedural{background:rgba(16,185,129,.15);color:var(--success)}
.badge-temporal{background:rgba(148,163,184,.15);color:var(--text2)}
.badge-relation{background:rgba(139,92,246,.15);color:var(--accent2)}
.badge-red{background:rgba(239,68,68,.2);color:#fca5a5}
.badge-immediate{background:rgba(6,182,212,.15);color:var(--accent)}
.badge-consolidated{background:rgba(139,92,246,.15);color:var(--accent2)}
.badge-timeless{background:rgba(16,185,129,.15);color:var(--success)}
.actions{margin-top:10px;display:flex;gap:8px;flex-wrap:wrap}
.actions input{font-size:12px}
.pre{margin-top:10px;font-family:var(--mono);font-size:12px;max-height:300px;overflow:auto;white-space:pre-wrap;background:var(--bg);padding:10px;border-radius:6px;border:1px solid var(--border)}
.progress{height:6px;border-radius:3px;background:var(--border);overflow:hidden;margin-top:6px}
.progress .fill{height:100%;border-radius:3px;transition:width .4s}
.fill-accent{background:var(--accent)}
.fill-success{background:var(--success)}
.fill-warning{background:var(--warning)}
.fill-error{background:var(--error)}
svg.chart{width:100%;height:80px;margin-top:8px}
.chart-line{fill:none;stroke:var(--accent);stroke-width:2}
.chart-area{fill:rgba(6,182,212,.1)}
.chart-grid{stroke:var(--border);stroke-width:.5}
.empty{color:var(--text3);font-style:italic;font-size:13px;padding:8px 0}
.row{display:flex;gap:8px;align-items:center}
.stat-row{display:flex;gap:20px;flex-wrap:wrap;margin-top:8px}
.stat{display:flex;flex-direction:column}
.stat .val{font-size:20px;font-weight:700}
.stat .lbl{font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:.5px}
</style>
</head>
<body>
<div class="topbar">
<h1>pneural-context<span class="ver">v1.0</span></h1>
<div class="spacer"></div>
<select id="project-select"><option value="">Select project...</option></select>
<input id="project-input" placeholder="Or type project..." style="max-width:180px">
<button onclick="loadProject()">Load</button>
<button onclick="refreshAll()">Refresh</button>
</div>
<div class="grid">
<div class="card" id="card-memory">
<h2><span class="icon">&#9776;</span> Memory</h2>
<div class="big-num" id="memory-count">—</div>
<div class="sub" id="memory-sub"></div>
<div class="stat-row" id="memory-stats"></div>
<ul class="list" id="memory-list"></ul>
</div>
<div class="card" id="card-redink">
<h2><span class="icon">&#9888;</span> Red Ink</h2>
<div class="big-num" id="redink-count">—</div>
<ul class="list" id="redink-list"></ul>
</div>
<div class="card" id="card-procedural">
<h2><span class="icon">&#9881;</span> Procedural</h2>
<div class="big-num" id="proc-count">—</div>
<div class="sub" id="proc-sub"></div>
<ul class="list" id="proc-list"></ul>
</div>
<div class="card" id="card-consolidation">
<h2><span class="icon">&#128228;</span> Consolidation</h2>
<div class="big-num" id="consol-count">—</div>
<div class="sub" id="consol-tiers"></div>
<ul class="list" id="consol-list"></ul>
<div class="actions">
<button onclick="triggerConsolidation()">Run Consolidation</button>
</div>
</div>
<div class="card" id="card-decay">
<h2><span class="icon">&#9202;</span> Decay</h2>
<div class="big-num" id="decay-weak">—</div>
<div class="sub" id="decay-sub"></div>
<div class="stat-row" id="decay-stats"></div>
<div class="actions">
<button onclick="triggerDecay()">Apply Decay</button>
<button onclick="archiveDecay()">Archive Weak</button>
</div>
</div>
<div class="card" id="card-costs">
<h2><span class="icon">&#128176;</span> Costs</h2>
<div class="stat-row" id="cost-stats"></div>
<svg class="chart" id="cost-chart"></svg>
</div>
<div class="card" id="card-anchors">
<h2><span class="icon">&#9875;</span> Anchors</h2>
<div class="stat-row" id="anchor-stats"></div>
<ul class="list" id="anchor-list"></ul>
</div>
<div class="card" id="card-briefing">
<h2><span class="icon">&#128196;</span> Briefing</h2>
<div class="actions">
<input id="briefing-task" placeholder="Task description..." style="flex:1">
<button onclick="generateBriefing()">Generate</button>
</div>
<pre class="pre" id="briefing-content"></pre>
</div>
</div>
<script>
const BASE='';
let P='"""
        + proj
        + """';
let refreshTimer=null;
function esc(s){const d=document.createElement('div');d.textContent=s;return d.innerHTML}
async function api(path,opts){try{const r=await fetch(BASE+path,opts);if(!r.ok)throw new Error(r.status+' '+r.statusText);return await r.json()}catch(e){console.error('API error:',e);return null}}

async function loadProjects(){
  const data=await api('/api/projects');
  const sel=document.getElementById('project-select');
  if(!data||!Array.isArray(data))return;
  sel.innerHTML='<option value="">Select project...</option>';
  data.forEach(p=>{const o=document.createElement('option');o.value=p;o.textContent=p;if(p===P)o.selected=true;sel.appendChild(o)});
}
document.getElementById('project-select').addEventListener('change',function(){if(this.value){P=this.value;document.getElementById('project-input').value=P;refreshAll()}});

async function loadProject(){P=document.getElementById('project-input').value.trim();if(!P)return;await refreshAll()}
async function refreshAll(){if(!P)return;const p=encodeURIComponent(P);const[memory,redInk,procs,consol,decay,anchors,costs]=await Promise.all([api('/api/memory/full?project='+p),api('/api/memory/red-ink?project='+p),api('/api/procedures?project='+p),api('/api/consolidation/status?project='+p),api('/api/decay/status?project='+p),api('/api/anchors?project='+p),api('/api/costs/summary?project='+p)]);renderMemory(memory);renderRedInk(redInk);renderProcs(procs);renderConsol(consol);renderDecay(decay);renderAnchors(anchors);renderCosts(costs);loadCostChart()}

function renderMemory(data){
  const el=document.getElementById('memory-count');
  const list=document.getElementById('memory-list');
  const stats=document.getElementById('memory-stats');
  if(!data){el.textContent='0';list.innerHTML='<li class="empty">No data</li>';stats.innerHTML='';return}
  const entries=Array.isArray(data)?data:[];
  el.textContent=entries.length;
  const types={};const prios={};
  entries.forEach(e=>{const t=e.memory_type||'temporal';const p=e.priority||'normal';types[t]=(types[t]||0)+1;prios[p]=(prios[p]||0)+1});
  document.getElementById('memory-sub').textContent=Object.entries(types).map(([k,v])=>k+':'+v).join(' ');
  let statsHtml='';
  for(const[k,v]of Object.entries(prios)){statsHtml+='<div class="stat"><span class="val">'+v+'</span><span class="lbl">'+k+'</span></div>'}
  for(const[k,v]of Object.entries(types)){statsHtml+='<div class="stat"><span class="val">'+v+'</span><span class="lbl">'+k+'</span></div>'}
  stats.innerHTML=statsHtml;
  list.innerHTML=entries.slice(0,12).map(e=>'<li><span class="badge badge-'+(e.memory_type||'temporal')+'">'+(e.memory_type||'temporal')+'</span><span class="badge badge-'+(e.priority||'normal')+'">'+(e.priority||'normal')+'</span> '+esc(e.entry||'').slice(0,80)+'</li>').join('');
}

function renderRedInk(data){
  const el=document.getElementById('redink-count');
  const list=document.getElementById('redink-list');
  if(!data){el.textContent='0';list.innerHTML='<li class="empty">No red ink</li>';return}
  const entries=Array.isArray(data)?data:[];
  el.textContent=entries.length;
  list.innerHTML=entries.slice(0,10).map(e=>'<li><span class="badge badge-red">CRITICAL</span> '+esc(e.entry||'').slice(0,100)+'</li>').join('')||'<li class="empty">No critical entries</li>';
}

function renderProcs(data){
  const el=document.getElementById('proc-count');
  const list=document.getElementById('proc-list');
  const sub=document.getElementById('proc-sub');
  if(!data){el.textContent='0';list.innerHTML='';sub.textContent='';return}
  const procs=Array.isArray(data)?data:[];
  el.textContent=procs.length;
  const avgScore=procs.length?(procs.reduce((s,p)=>(s+(p.reinforcement_score||0)),0)/procs.length).toFixed(2):'0';
  sub.textContent='avg score: '+avgScore;
  list.innerHTML=procs.slice(0,8).map(p=>'<li><span class="badge badge-'+(p.task_type||'task')+'">'+(p.task_type||'task')+'</span> '+esc(p.task_pattern||'').slice(0,70)+' <small style="color:var(--text3)">score:'+((p.reinforcement_score||0)*100).toFixed(0)+'%</small></li>').join('');
}

function renderConsol(data){
  const el=document.getElementById('consol-count');
  const sub=document.getElementById('consol-tiers');
  const list=document.getElementById('consol-list');
  if(!data){el.textContent='—';sub.textContent='';list.innerHTML='';return}
  const tiers=data.tiers||{};
  const total=data.total||Object.values(tiers).reduce((a,b)=>a+b,0);
  el.textContent=total;
  sub.textContent=Object.entries(tiers).map(([k,v])=>k+':'+v).join(' | ');
  list.innerHTML='';
  for(const[tier,count]of Object.entries(tiers)){
    list.innerHTML+='<li><span class="badge badge-'+tier+'">'+tier+'</span> '+count+' entries</li>';
  }
}

function renderDecay(data){
  const el=document.getElementById('decay-weak');
  const sub=document.getElementById('decay-sub');
  const stats=document.getElementById('decay-stats');
  if(!data){el.textContent='—';sub.textContent='';stats.innerHTML='';return}
  el.textContent=(data.below_threshold||0)+' weak';
  sub.textContent='total: '+(data.total||0);
  let statsHtml='<div class="stat"><span class="val">'+(data.fading||0)+'</span><span class="lbl">fading</span></div>';
  statsHtml+='<div class="stat"><span class="val">'+(data.stable||0)+'</span><span class="lbl">stable</span></div>';
  stats.innerHTML=statsHtml;
}

function renderAnchors(data){
  const list=document.getElementById('anchor-list');
  const stats=document.getElementById('anchor-stats');
  if(!data){list.innerHTML='';stats.innerHTML='';return}
  let statsHtml='<div class="stat"><span class="val">'+(data.active_memory_count||0)+'</span><span class="lbl">memory</span></div>';
  statsHtml+='<div class="stat"><span class="val">'+(data.red_ink_count||0)+'</span><span class="lbl">red ink</span></div>';
  statsHtml+='<div class="stat"><span class="val">'+(data.procedures_count||0)+'</span><span class="lbl">procs</span></div>';
  stats.innerHTML=statsHtml;
  let html='';
  if(data.red_ink_reminders&&data.red_ink_reminders.length){html+='<li><strong>Red Ink:</strong> '+data.red_ink_reminders.map(r=>esc(r.entry||'').slice(0,60)).join(', ')+'</li>'}
  if(data.top_procedures&&data.top_procedures.length){html+='<li><strong>Top Procs:</strong> '+data.top_procedures.map(p=>esc(p.pattern||'').slice(0,40)).join(', ')+'</li>'}
  if(data.recent_entries&&data.recent_entries.length){html+='<li><strong>Recent:</strong> '+data.recent_entries.length+' entries</li>'}
  if(data.priority_distribution){html+='<li><strong>Priority:</strong> '+Object.entries(data.priority_distribution).map(([k,v])=>k+':'+v).join(' ')+'</li>'}
  list.innerHTML=html||'<li class="empty">No anchors</li>';
}

function renderCosts(data){
  const stats=document.getElementById('cost-stats');
  if(!data){stats.innerHTML='<div class="empty">No cost data</div>';return}
  let html='<div class="stat"><span class="val">'+(data.total_injected||0).toLocaleString()+'</span><span class="lbl">injected</span></div>';
  html+='<div class="stat"><span class="val">'+(data.total_saved_injection||0).toLocaleString()+'</span><span class="lbl">saved inj</span></div>';
  html+='<div class="stat"><span class="val">'+(data.total_saved_forgetting||0).toLocaleString()+'</span><span class="lbl">saved decay</span></div>';
  html+='<div class="stat"><span class="val">'+(data.count||0)+'</span><span class="lbl">records</span></div>';
  stats.innerHTML=html;
}

async function loadCostChart(){
  if(!P)return;
  const data=await api('/api/costs/trends?project='+encodeURIComponent(P)+'&days=30');
  const svg=document.getElementById('cost-chart');
  if(!data||!Array.isArray(data)||data.length===0){svg.innerHTML='<text x="50%" y="50%" text-anchor="middle" fill="var(--text3)" font-size="12">No trend data</text>';return}
  const w=400;const h=80;const pad=2;
  const maxVal=Math.max(...data.map(d=>d.tokens_injected||0),1);
  const points=data.map((d,i)=>{const x=pad+(i/(data.length-1||1))*(w-2*pad);const y=h-pad-((d.tokens_injected||0)/maxVal)*(h-2*pad);return x+','+y});
  const areaPoints=points.join(' ')+' '+(w-pad)+','+(h-pad)+' '+pad+','+(h-pad);
  svg.setAttribute('viewBox','0 0 '+w+' '+h);
  svg.innerHTML='<polyline points="'+points.join(' ')+'" class="chart-line"/><polygon points="'+areaPoints+'" class="chart-area"/>';
}

async function triggerConsolidation(){if(!P)return;await api('/api/consolidation',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:P})});refreshAll()}
async function triggerDecay(){if(!P)return;await api('/api/decay',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:P})});refreshAll()}
async function archiveDecay(){if(!P)return;await api('/api/decay/archive',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:P})});refreshAll()}
async function generateBriefing(){if(!P)return;const task=document.getElementById('briefing-task').value.trim();const p=encodeURIComponent(P);let url='/api/briefing?project='+p;if(task)url+='&task='+encodeURIComponent(task);const data=await api(url);const el=document.getElementById('briefing-content');if(data&&data.briefing)el.textContent=data.briefing;else el.textContent='No briefing generated'}

if(P){loadProjects();refreshAll()}else{loadProjects()}
refreshTimer=setInterval(()=>{if(P)refreshAll()},30000);
</script>
</body>
</html>"""
    )
