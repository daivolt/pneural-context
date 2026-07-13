from __future__ import annotations

import json


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
.topbar button.secondary{background:var(--surface);color:var(--text2);border:1px solid var(--border)}
.topbar button.secondary:hover{border-color:var(--accent);color:var(--text)}
.tab-bar{display:flex;gap:0;padding:0 24px;background:var(--surface);border-bottom:1px solid var(--border)}
.tab-bar button{background:none;border:none;border-bottom:2px solid transparent;color:var(--text3);padding:10px 16px;font-size:13px;font-weight:500;cursor:pointer;transition:all .2s}
.tab-bar button:hover{color:var(--text)}
.tab-bar button.active{color:var(--accent);border-bottom-color:var(--accent)}
.tab-content{display:none;padding:20px 24px}
.tab-content.active{display:block}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px}
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
.btn{font-family:inherit;font-size:12px;border:1px solid var(--border);border-radius:6px;padding:5px 12px;background:var(--bg);color:var(--text);cursor:pointer;transition:all .2s}
.btn:hover{border-color:var(--accent);color:var(--accent)}
.btn.primary{background:var(--accent);color:#000;border:none;font-weight:600}
.btn.primary:hover{opacity:.85}
.btn.danger{background:rgba(239,68,68,.15);color:var(--error);border-color:rgba(239,68,68,.3)}
.btn.danger:hover{background:rgba(239,68,68,.25)}
.pre{margin-top:10px;font-family:var(--mono);font-size:12px;max-height:400px;overflow:auto;white-space:pre-wrap;background:var(--bg);padding:10px;border-radius:6px;border:1px solid var(--border)}
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
.form-group{margin-bottom:12px}
.form-group label{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:var(--text3);margin-bottom:4px}
.form-group input,.form-group select,.form-group textarea{width:100%;font-family:inherit;font-size:13px;border:1px solid var(--border);border-radius:6px;padding:8px 12px;background:var(--bg);color:var(--text);outline:none}
.form-group input:focus,.form-group select:focus,.form-group textarea:focus{border-color:var(--accent)}
.form-group textarea{min-height:60px;resize:vertical}
.form-row{display:flex;gap:12px}
.form-row .form-group{flex:1}
.settings-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.toast{position:fixed;bottom:20px;right:20px;padding:12px 20px;border-radius:8px;font-size:13px;font-weight:500;z-index:1000;opacity:0;transition:opacity .3s}
.toast.show{opacity:1}
.toast.success{background:var(--success);color:#000}
.toast.error{background:var(--error);color:#fff}
.modal-overlay{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.6);z-index:100;align-items:center;justify-content:center}
.modal-overlay.show{display:flex}
.modal{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:24px;max-width:500px;width:90%;max-height:80vh;overflow-y:auto}
.modal h3{margin-bottom:16px;font-size:16px}
.modal .actions{margin-top:16px;justify-content:flex-end}
</style>
</head>
<body>
<div class="topbar">
<h1>pneural-context<span class="ver">v0.1.0a1</span></h1>
<div class="spacer"></div>
<select id="project-select"><option value="">Select project...</option></select>
<input id="project-input" placeholder="Or type project..." style="max-width:180px">
<button class="primary" onclick="loadProject()">Load</button>
<button class="secondary" onclick="refreshAll()">Refresh</button>
</div>
<div class="tab-bar">
<button class="active" onclick="switchTab('overview')">Overview</button>
<button onclick="switchTab('memory')">Memory</button>
<button onclick="switchTab('context')">Context</button>
<button onclick="switchTab('settings')">Settings</button>
</div>

<div id="tab-overview" class="tab-content active">
<div class="grid">
<div class="card" id="card-memory">
<h2><span class="icon">&#9776;</span> Memory</h2>
<div class="big-num" id="memory-count">&mdash;</div>
<div class="sub" id="memory-sub"></div>
<div class="stat-row" id="memory-stats"></div>
</div>
<div class="card" id="card-redink">
<h2><span class="icon">&#9888;</span> Red Ink</h2>
<div class="big-num" id="redink-count">&mdash;</div>
<ul class="list" id="redink-list"></ul>
</div>
<div class="card" id="card-procedural">
<h2><span class="icon">&#9881;</span> Procedural</h2>
<div class="big-num" id="proc-count">&mdash;</div>
<div class="sub" id="proc-sub"></div>
<ul class="list" id="proc-list"></ul>
</div>
<div class="card" id="card-consolidation">
<h2><span class="icon">&#128228;</span> Consolidation</h2>
<div class="big-num" id="consol-count">&mdash;</div>
<div class="sub" id="consol-tiers"></div>
<ul class="list" id="consol-list"></ul>
<div class="actions">
<button class="btn primary" onclick="triggerConsolidation()">Run Consolidation</button>
</div>
</div>
<div class="card" id="card-decay">
<h2><span class="icon">&#9202;</span> Decay</h2>
<div class="big-num" id="decay-weak">&mdash;</div>
<div class="sub" id="decay-sub"></div>
<div class="stat-row" id="decay-stats"></div>
<div class="actions">
<button class="btn" onclick="triggerDecay()">Apply Decay</button>
<button class="btn danger" onclick="archiveDecay()">Archive Weak</button>
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
<button class="btn primary" onclick="generateBriefing()">Generate</button>
</div>
<pre class="pre" id="briefing-content"></pre>
</div>
</div>
</div>

<div id="tab-memory" class="tab-content">
<div class="grid">
<div class="card">
<h2><span class="icon">&#10133;</span> Add Memory</h2>
<div class="form-group">
<label>Text</label>
<textarea id="mem-add-text" placeholder="Enter memory text..."></textarea>
</div>
<div class="form-row">
<div class="form-group">
<label>Priority</label>
<select id="mem-add-priority">
<option value="normal">Normal</option>
<option value="important">Important</option>
<option value="critical">Critical</option>
</select>
</div>
<div class="form-group">
<label>Type</label>
<select id="mem-add-type">
<option value="">Auto</option>
<option value="red">Red</option>
<option value="concept">Concept</option>
<option value="procedural">Procedural</option>
<option value="temporal">Temporal</option>
<option value="relation">Relation</option>
</select>
</div>
</div>
<div class="actions">
<button class="btn primary" onclick="addMemory()">Add Memory</button>
<button class="btn" onclick="classifyMemory()">Auto-Classify All</button>
</div>
</div>
<div class="card">
<h2><span class="icon">&#9776;</span> All Entries</h2>
<div class="actions" style="margin-bottom:8px">
<input id="mem-search" placeholder="Filter entries..." style="flex:1" oninput="filterMemory()">
</div>
<div id="memory-full-list" style="max-height:500px;overflow-y:auto"></div>
</div>
</div>
</div>

<div id="tab-context" class="tab-content">
<div class="card">
<h2><span class="icon">&#128196;</span> Injection Context Preview</h2>
<p class="sub" style="margin-bottom:8px">This is what gets injected into the system prompt via <code>/api/context</code></p>
<div class="actions">
<button class="btn primary" onclick="loadContext()">Load Context</button>
<button class="btn" onclick="copyContext()">Copy to Clipboard</button>
</div>
<pre class="pre" id="context-markdown" style="max-height:600px"></pre>
<div class="stat-row" id="context-stats" style="margin-top:12px"></div>
</div>
</div>

<div id="tab-settings" class="tab-content">
<div class="settings-grid">
<div class="card">
<h2><span class="icon">&#9881;</span> LLM Configuration</h2>
<div class="form-group">
<label>LLM URL</label>
<input id="cfg-llm-url" placeholder="http://localhost:12345/v1">
</div>
<div class="form-group">
<label>LLM Model</label>
<input id="cfg-llm-model" placeholder="local-model">
</div>
<div class="form-group">
<label>LLM API Key</label>
<input id="cfg-llm-api-key" type="password" placeholder="(hidden)">
</div>
<div class="actions">
<button class="btn primary" onclick="saveSettings()">Save</button>
<button class="btn" onclick="loadSettings()">Reset</button>
</div>
</div>
<div class="card">
<h2><span class="icon">&#9202;</span> Decay &amp; Consolidation</h2>
<div class="form-group">
<label>Decay Interval (seconds)</label>
<input id="cfg-decay-interval" type="number" placeholder="21600">
</div>
<div class="form-group">
<label>Consolidation Interval (seconds)</label>
<input id="cfg-consol-interval" type="number" placeholder="21600">
</div>
<div class="form-group">
<label>Archive Threshold</label>
<input id="cfg-archive-threshold" type="number" step="0.01" placeholder="0.1">
</div>
<div class="actions">
<button class="btn primary" onclick="saveSettings()">Save</button>
</div>
</div>
<div class="card">
<h2><span class="icon">&#128279;</span> Memoria Integration</h2>
<div class="form-group">
<label>Memoria URL</label>
<input id="cfg-memoria-url" placeholder="http://localhost:8766">
</div>
<div class="form-group">
<label>Enabled</label>
<select id="cfg-memoria-enabled">
<option value="false">Disabled</option>
<option value="true">Enabled</option>
</select>
</div>
<div class="actions">
<button class="btn primary" onclick="saveSettings()">Save</button>
</div>
</div>
<div class="card">
<h2><span class="icon">&#2139;</span> Current Config</h2>
<pre class="pre" id="config-display" style="max-height:300px"></pre>
</div>
</div>
</div>

<div class="modal-overlay" id="modal-overlay">
<div class="modal" id="modal-content"></div>
</div>
<div class="toast" id="toast"></div>

<script>
const BASE='';
let P=JSON.parse('"""
        + json.dumps(proj)
        + """');
let refreshTimer=null;
let currentTab='overview';
let contextData=null;

function esc(s){const d=document.createElement('div');d.textContent=s;return d.innerHTML}

function showToast(msg,type='success'){const t=document.getElementById('toast');t.textContent=msg;t.className='toast '+type+' show';setTimeout(()=>t.classList.remove('show'),3000)}

function switchTab(tab){currentTab=tab;document.querySelectorAll('.tab-bar button').forEach(b=>b.classList.remove('active'));document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));event.target.classList.add('active');document.getElementById('tab-'+tab).classList.add('active');if(tab==='settings')loadSettings()}

function showModal(title,bodyHtml){const overlay=document.getElementById('modal-overlay');const content=document.getElementById('modal-content');content.innerHTML='<h3>'+esc(title)+'</h3>'+bodyHtml+'<div class="actions" style="margin-top:16px;justify-content:flex-end"><button class="btn" onclick="closeModal()">Close</button></div>';overlay.classList.add('show')}
function closeModal(){document.getElementById('modal-overlay').classList.remove('show')}
document.getElementById('modal-overlay').addEventListener('click',function(e){if(e.target===this)closeModal()});

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
async function refreshAll(){if(!P)return;const p=encodeURIComponent(P);const[memory,redInk,procs,consol,decay,anchors,costs]=await Promise.all([api('/api/memory/full?project='+p),api('/api/memory/red-ink?project='+p),api('/api/procedures?project='+p),api('/api/consolidation/status?project='+p),api('/api/decay/status?project='+p),api('/api/anchors?project='+p),api('/api/costs/summary?project='+p)]);renderMemory(memory);renderRedInk(redInk);renderProcs(procs);renderConsol(consol);renderDecay(decay);renderAnchors(anchors);renderCosts(costs);loadCostChart();renderMemoryList(memory)}

function renderMemory(data){
  const el=document.getElementById('memory-count');
  const stats=document.getElementById('memory-stats');
  if(!data){el.textContent='0';stats.innerHTML='';return}
  const entries=Array.isArray(data)?data:[];
  el.textContent=entries.length;
  const types={};const prios={};
  entries.forEach(e=>{const t=e.memory_type||'temporal';const p=e.priority||'normal';types[t]=(types[t]||0)+1;prios[p]=(prios[p]||0)+1});
  document.getElementById('memory-sub').textContent=Object.entries(types).map(([k,v])=>k+':'+v).join(' ');
  let statsHtml='';
  for(const[k,v]of Object.entries(prios)){statsHtml+='<div class="stat"><span class="val">'+v+'</span><span class="lbl">'+k+'</span></div>'}
  for(const[k,v]of Object.entries(types)){statsHtml+='<div class="stat"><span class="val">'+v+'</span><span class="lbl">'+k+'</span></div>'}
  stats.innerHTML=statsHtml;
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

function renderMemoryList(data){
  const container=document.getElementById('memory-full-list');
  if(!data||!Array.isArray(data)||data.length===0){container.innerHTML='<div class="empty">No memory entries</div>';return}
  const filter=(document.getElementById('mem-search')||{}).value||''.toLowerCase();
  let entries=data;
  if(filter){entries=entries.filter(e=>(e.entry||'').toLowerCase().includes(filter))}
  container.innerHTML=entries.map((e,i)=>'<div style="padding:6px 0;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:8px"><span class="badge badge-'+(e.priority||'normal')+'">'+(e.priority||'normal')+'</span><span class="badge badge-'+(e.memory_type||'temporal')+'">'+(e.memory_type||'temporal')+'</span><span style="flex:1;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+esc(e.entry||'')+'</span><span style="font-size:11px;color:var(--text3)">'+(e.strength!=null?'s:'+e.strength.toFixed(2):'')+'</span><button class="btn danger" style="padding:2px 8px;font-size:11px" onclick="deleteEntry('+e.id+')">x</button><button class="btn" style="padding:2px 8px;font-size:11px" onclick="boostEntry('+e.id+')">+</button></div>').join('');
}

function filterMemory(){refreshAll()}

async function addMemory(){
  if(!P)return;
  const text=document.getElementById('mem-add-text').value.trim();
  if(!text){showToast('Text required','error');return}
  const priority=document.getElementById('mem-add-priority').value;
  const memory_type=document.getElementById('mem-add-type').value||undefined;
  const body={project:P,text:text,priority:priority};
  if(memory_type)body.memory_type=memory_type;
  const result=await api('/api/memory',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(result&&result.id){showToast('Memory added (id='+result.id+')');document.getElementById('mem-add-text').value='';refreshAll()}else{showToast('Failed to add memory','error')}
}

async function deleteEntry(id){
  if(!P)return;
  const result=await api('/api/memory/'+id+'?project='+encodeURIComponent(P),{method:'DELETE'});
  if(result&&result.ok){showToast('Entry deleted');refreshAll()}else{showToast('Failed to delete','error')}
}

async function boostEntry(id){
  if(!P)return;
  const result=await api('/api/memory/boost',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:P,index:id})});
  if(result&&result.ok){showToast('Entry boosted');refreshAll()}else{showToast('Failed to boost','error')}
}

async function classifyMemory(){
  if(!P)return;
  const result=await api('/api/memory/classify',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:P})});
  if(result){showToast('Classification triggered');refreshAll()}else{showToast('Failed to classify','error')}
}

async function loadContext(){
  if(!P)return;
  contextData=await api('/api/context?project='+encodeURIComponent(P));
  const el=document.getElementById('context-markdown');
  const stats=document.getElementById('context-stats');
  if(!contextData){el.textContent='No context data';stats.innerHTML='';return}
  el.textContent=contextData.markdown||contextData.context||'';
  let statsHtml='<div class="stat"><span class="val">'+(contextData.entries||0)+'</span><span class="lbl">entries</span></div>';
  statsHtml+='<div class="stat"><span class="val">'+(contextData.consolidated_entries||0)+'</span><span class="lbl">consolidated</span></div>';
  statsHtml+='<div class="stat"><span class="val">'+(contextData.red_ink_entries||[]).length+'</span><span class="lbl">red ink</span></div>';
  statsHtml+='<div class="stat"><span class="val" style="font-family:var(--mono);font-size:14px">'+(contextData.marker||'')+'</span><span class="lbl">marker</span></div>';
  stats.innerHTML=statsHtml;
}

function copyContext(){
  if(!contextData)return;
  const text=contextData.markdown||contextData.context||'';
  navigator.clipboard.writeText(text).then(()=>showToast('Copied to clipboard')).catch(()=>showToast('Copy failed','error'));
}

async function loadSettings(){
  const data=await api('/api/config');
  if(!data)return;
  document.getElementById('cfg-llm-url').value=data.llm_url||'';
  document.getElementById('cfg-llm-model').value=data.llm_model||'';
  document.getElementById('cfg-llm-api-key').value=data.llm_api_key_set?'(set)':'';
  document.getElementById('cfg-decay-interval').value=data.decay_interval_seconds||'';
  document.getElementById('cfg-consol-interval').value=data.consolidation_interval_seconds||'';
  document.getElementById('cfg-archive-threshold').value=data.archive_threshold||'';
  document.getElementById('cfg-memoria-url').value=data.memoria_url||'';
  document.getElementById('cfg-memoria-enabled').value=data.memoria_enabled?'true':'false';
  const display=document.getElementById('config-display');
  const safe=JSON.stringify(data,null,2);
  display.textContent=safe;
}

async function saveSettings(){
  const updates={};
  const llmUrl=document.getElementById('cfg-llm-url').value.trim();
  const llmModel=document.getElementById('cfg-llm-model').value.trim();
  const decayInterval=document.getElementById('cfg-decay-interval').value.trim();
  const consolInterval=document.getElementById('cfg-consol-interval').value.trim();
  const archiveThreshold=document.getElementById('cfg-archive-threshold').value.trim();
  const memoriaUrl=document.getElementById('cfg-memoria-url').value.trim();
  const memoriaEnabled=document.getElementById('cfg-memoria-enabled').value;
  if(llmUrl)updates.llm_url=llmUrl;
  if(llmModel)updates.llm_model=llmModel;
  if(decayInterval)updates.decay_interval_seconds=parseFloat(decayInterval);
  if(consolInterval)updates.consolidation_interval_seconds=parseFloat(consolInterval);
  if(archiveThreshold)updates.archive_threshold=parseFloat(archiveThreshold);
  if(memoriaUrl)updates.memoria_url=memoriaUrl;
  updates.memoria_enabled=memoriaEnabled==='true';
  const result=await api('/api/config',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(updates)});
  if(result&&result.ok){showToast('Settings saved');loadSettings()}else{showToast('Failed to save settings','error')}
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
