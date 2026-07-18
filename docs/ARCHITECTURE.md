# Pneural-Context Architecture

## Machine Topology

```
                    LAN 10.42.0.0/24
       mediserv (PROD)              desktop-ryzen (DEV)
       100.126.64.13 TS            100.117.7.2 TS
       10.42.0.213                 10.42.0.89
       ┌───────────────────┐       ┌────────────────────────┐
       │ pneural-context    │       │ llama-server.exe       │
       │ systemd :8778      │──────►│ :8080 (turboquant)     │
       │                    │ 8080  │ qwen2.5-coder-7b Q4   │
       └───────────────────┘       └────────────────────────┘
       ┌───────────────────┐       ┌────────────────────────┐
       │ ollama             │       │ pneural-context         │
       │ :11434             │       │ ScheduledTask :8779    │
       │ nomic-embed-text   │       │ DB: pneural_test       │
       └───────────────────┘       └────────────────────────┘
       ┌───────────────────┐       ┌────────────────────────┐
       │ PostgreSQL 18.3    │       │ opencode serve          │
       │ DB: pneural_context│       │ port 4096              │
       └───────────────────┘       └────────────────────────┘
       ┌───────────────────┐
       │ opencode + plugin  │
       └───────────────────┘
```

## Data Flow

```
opencode session
  │
  ├─ system.transform ──► plugin ──► GET /api/context ──► pb_memory + pb_consolidated
  │                      (fetchContext)                    (3-tier cortex)
  │
  ├─ session.idle ──────► plugin ──► POST /api/session/record ──► pb_memory
  ├─ session.error ─────► plugin ──► POST /api/errors ──► pb_errors
  │
  └─ session.compacting ► plugin ──► preserve PNEURAL_CTX markers
```

## Component Layout

```
pneural_context/
├── server.py          FastAPI app, lifespan, background tasks (decay, consolidation)
├── pb_config.py       Pydantic settings from env vars
├── pb_engine.py       Consolidation pipeline (3-tier cortex)
├── pb_llm.py          LLM client (OpenAI-compatible API)
├── pb_embeddings.py   Embedding backends (ollama, sentence-transformers)
├── pb_memoria.py      Memoria integration bridge
├── pb_db.py           Database pool + search init
├── routers/           FastAPI routers (16 modules)
│   ├── status.py      Enable/disable toggle
│   ├── errors.py      Telemetry / error capture
│   ├── memory.py      CRUD for pb_memory
│   ├── context.py     Context assembly (full + smart dedup)
│   └── ...
├── mcp_server/        MCP stdio server (separate process)
│   └── server.py      31 MCP tools
└── db/                DB access layer
    ├── pool.py, memory.py, search.py
    ├── consolidated.py, procedures.py
    └── costs.py, decay.py, dedup.py, utils.py
```

## Database

PostgreSQL with pgvector (768-dim). Tables:
- `pb_memory` — per-project memory entries
- `pb_consolidated_memory` — 3-tier cortex (immediate/consolidated/timeless)
- `pb_procedural_memory` — basal ganglia procedural patterns
- `pb_memory_costs` — token cost analytics
- `pb_memory_archive` — decayed entries (searchable)
- `pb_papers` — research paper index
- `pb_errors` — telemetry / error capture

## Background Tasks

- **Decay loop** (PNEURAL_DECAY_INTERVAL, default 6h): Ebbinghaus exponential decay
- **Consolidation loop** (PNEURAL_CONSOLIDATION_INTERVAL, default 6h): 3-tier cortex pipeline

## LLM / Embedding Topology

| Machine | LLM | Embedding |
|---------|-----|-----------|
| mediserv (prod) | ryzen:8080 via LAN | local ollama :11434 |
| desktop-ryzen (dev) | local :8080 | local ollama :11434 |
