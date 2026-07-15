# pneural-context

> **⚠️ EXPERIMENTAL ALPHA — UNDER CONSTRUCTION**
>
> This software is in early alpha and actively under development.
> APIs will change without notice. Things will break. Data schemas may
> be incompatible between versions. No migration paths are guaranteed.
> Features may be incomplete or non-functional. Use at your own risk.

## What Is This

pneural-context is a persistent neural context layer for LLM agents — memory, consolidation, decay, and recall. LLMs have anterograde amnesia: every session starts from scratch, and context compaction loses information the way anterograde amnesia destroys continuity. pneural-context stores, consolidates, decays, and recalls context so an agent can recover relevant memory at the start of a new session.

## Goal

Give LLM agents a durable memory layer that outlives session death — so work done in one session is recoverable in the next.

## Inspired By

- **Junko Mizuta** — a Japanese woman who, after herpes simplex virus damaged her brain in the 2000s, was left with approximately 7 seconds of short-term memory. Documented in the CBC (Chubu-Nippon Broadcasting) documentary *Ever Vanishing Present* (dir. Toshihiro Matsumoto, 2017), she coped by carrying a blue notebook everywhere, writing down what she did, who she spoke to, and where she went — trying to anchor herself in a present that kept dissolving. She said: "I want to leave it in a tangible form, so I'm engrossed in taking notes now" Over time the volume of notebooks became unmanageable; when moving in with relatives, she shredded months of her own notes. CBC followed her for years, and the documentary — whose tagline is "Memory is Life" — shows she eventually stopped taking memos entirely. She also taught herself a driving route to a local supermarket through sheer repetition, an example of procedural memory surviving where declarative memory could not. This paradox — notes as both lifeline and burden, the choice to stop writing rather than drown in paper — directly motivated our design: pneural-context has a consolidation pipeline (to prevent unmanageable volume) and graceful forgetting via Ebbinghaus decay (accepting that not everything needs to be kept — as Mizuta herself demonstrated when she eventually stopped writing).

- **Clive Wearing** — a British musician who lost the ability to form new declarative memories after herpes simplex viral encephalitis in 1985, living in an eternal present with a ~7-30 second memory span. He filled diary after diary with entries like "8:31 AM: Now I am really, completely awake" — then crossed them out moments later, unable to recognize his own handwriting as real. Despite catastrophic amnesia, his procedural memory (conducting, playing piano) and emotional responses remained intact — he greeted his wife Deborah with joy every time he saw her, even moments after she'd left the room. This dissociation between destroyed declarative memory and preserved procedural/emotional memory directly motivated our separation of memory into five types (`red`, `concept`, `procedural`, `temporal`, `relation`) and our decision to give procedural entries higher decay resistance.

- **Hippocampal replay** — the neuroscience of how the brain consolidates experiences during sleep. During slow-wave sleep, hippocampal place cells reactivate in the same sequences as during waking experience (Wilson & McNaughton, 1994), transferring short-term traces to neocortical long-term storage. Our 3-tier consolidation pipeline (`immediate → consolidated → timeless`) directly mirrors this hippocampo-neocortical transfer.

- **Ebbinghaus forgetting curve** — the mathematical model of memory decay where unused memories fade exponentially unless refreshed through recall (Ebbinghaus, 1885/1913). Our decay system applies `strength *= 0.95` per consolidation cycle, and our `boost_entry` operation adds `+0.3` strength on access (capped at 1.0) — a computational implementation of the spaced repetition principle that Cepeda et al. (2006) meta-analytically confirmed produces ~2× better retention than massed practice.

### Scientific References

> *Under construction — citations being compiled.*

1. Ebbinghaus, H. (1913). *Memory: A contribution to experimental psychology* (H. A. Ruger & C. E. Bussenius, Trans.). New York: Teachers College, Columbia University. — The original forgetting curve: memory decays exponentially over time unless reinforced. Our decay model (`strength *= 0.95`) is a discretized approximation of this curve.

2. Murre, J. M. J., & Dros, J. (2015). Replication and analysis of Ebbinghaus' forgetting curve. *PLOS ONE*, 10(7), e0120644. https://doi.org/10.1371/journal.pone.0120644 — Validated Ebbinghaus' parameters with modern methods. Key finding: forgetting curves show a "jump" at 24 hours, suggesting a sleep-consolidation benefit. Supports our design where a consolidation cycle both decays AND consolidates.

3. Buzsáki, G. (1996). The hippocampo-neocortical dialogue. *Cerebral Cortex*, 6(2), 81–92. https://doi.org/10.1093/cercor/6.2.81 — The architectural blueprint for our 3-tier system. Describes two hippocampal modes: "open loop" (awake, information processing) and "closed loop" (sleep, sharp wave-ripple consolidation). Our `immediate` tier = open loop encoding; `run_consolidation()` = closed loop replay; `timeless` = neocortical permanent storage.

4. Diekelmann, S., & Born, J. (2010). The memory function of sleep. *Nature Reviews Neuroscience*, 11(2), 114–126. https://doi.org/10.1038/nrn2762 — Directly informed our consolidation timing and promotion logic. Key findings used: (1) SWS preferentially consolidates declarative memories; (2) sleep soon after learning is more effective (our `immediate` tier captures recent entries); (3) emotional/salient memories get prioritized (our `critical` priority auto-promotes to `timeless`); (4) explicit encoding is required for consolidation (we only consolidate explicitly-added memories).

5. Cepeda, N. J., Pashler, H., Vul, E., Wixted, J. T., & Rohrer, D. (2006). Distributed practice in verbal recall tasks: A review and quantitative synthesis. *Psychological Bulletin*, 132(3), 354–380. https://doi.org/10.1037/0033-2909.132.3.354 — The meta-analytic foundation for our boost/touch mechanism. Across 839 comparisons, spaced practice produces ~2× better retention than massed practice. Validates our `boost_entry` (+0.3 strength on recall/access) and our `archive_threshold = 0.1` (over-spacing reduces benefit, so forgotten entries are archived rather than rescued).

6. Wilson, M. A., & McNaughton, B. L. (1994). Reactivation of hippocampal ensemble memories during sleep. *Science*, 265(5172), 676–679. https://doi.org/10.1126/science.8036517 — First direct evidence that hippocampal cells replay waking experience sequences during sleep. The neurobiological basis for our `run_consolidation()` function: just as hippocampal cells replay experiences during sleep to transfer them to neocortex, our system replays recent entries to extract insights and promote them to consolidated/timeless tiers.

7. Wilson, B. A., Baddeley, A. D., & Kapur, N. (1995). Dense amnesia in a professional musician following herpes simplex virus encephalitis. *Journal of Clinical and Experimental Neuropsychology*, 17(5), 668–681. https://doi.org/10.1080/01688639508405157 — Clive Wearing's case: severe amnesia with preserved procedural and emotional memory. Despite 7-second memory span, Wearing could conduct music and play piano. This dissociation motivated our `memory_type` separation (procedural entries resist decay) and our red ink system (emotional/critical entries never fall below `strength = 0.5`).

---

pneural-context gives LLM agents:

- **Memory entries** with priority levels (critical/important/normal) and typed classification (red/concept/procedural/temporal/relation)
- **Automatic consolidation** that promotes frequently-accessed memories to higher tiers and archives forgotten ones
- **Spaced repetition** via boost/touch operations that strengthen memories before they decay
- **Decay** that gradually reduces memory strength over time, archiving entries below a threshold
- **Briefing cards** that assemble relevant context for a specific task
- **Procedural memory** that captures recurring task patterns and their outcomes
- **Cost tracking** for monitoring context injection efficiency

## Requirements

- Python 3.11+
- PostgreSQL 14+ (with `pg_trgm`, `uuid-ossp`, and `pgvector` extensions)
- An OpenAI-compatible LLM endpoint (LM Studio, Ollama, OpenAI, etc.)
- Ollama (for embeddings, default backend)

## Install

```bash
git clone https://github.com/daivolt/pneural-context.git
cd pneural-context
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

For optional Memoria integration:

```bash
pip install -e ".[memoria]"
```

For Python-based embeddings (alternative to Ollama):

```bash
pip install -e ".[embeddings]"
```

## Quick Start

### 1. Create the database

```sql
CREATE DATABASE pneural;
CREATE USER pneural WITH PASSWORD 'pneural_dev';
GRANT ALL PRIVILEGES ON DATABASE pneural TO pneural;
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your database URL and LLM endpoint
```

Or set environment variables directly:

```bash
export PNEURAL_DATABASE_URL="postgresql://pneural:pneural_dev@localhost:5432/pneural"
export PNEURAL_LLM_URL="http://localhost:12345/v1"
export PNEURAL_LLM_MODEL="local-model"
```

### 3. Run the server

```bash
pneural-context serve
```

The server starts on `http://0.0.0.0:8777`. Schema is auto-applied on first startup.

### 4. Use the API

```bash
# Add a memory
curl -X POST http://localhost:8777/api/memory \
  -H "Content-Type: application/json" \
  -d '{"project": "my-project", "text": "Important insight about X", "priority": "critical"}'

# Get assembled context for injection
curl "http://localhost:8777/api/context?project=my-project"

# Search memories
curl "http://localhost:8777/api/recall?project=my-project&q=insight"

# Generate a briefing for a task
curl "http://localhost:8777/api/briefing?project=my-project&task=implement+auth+system"

# Trigger consolidation
curl -X POST http://localhost:8777/api/consolidation \
  -h "Content-Type: application/json" \
  -d '{"project": "my-project"}'
```

## CLI

```bash
# Start the server
pneural-context serve --port 8777

# Add a memory
pneural-context memory add -p my-project -t "Some observation" --priority important

# List memories
pneural-context memory list -p my-project

# Run consolidation
pneural-context consolidation -p my-project

# Generate a briefing
pneural-context briefing -p my-project -t "debug the auth flow"

# Check decay status
pneural-context decay -p my-project

# View anchors
pneural-context anchors -p my-project
```

## REST API

All endpoints use the `/api/` prefix.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/memory` | Add a memory entry |
| `GET` | `/api/memory` | List memory entries |
| `POST` | `/api/memory/replace` | Replace a memory entry (find/replace text) |
| `GET` | `/api/memory/red-ink` | Get critical (red ink) entries |
| `PATCH` | `/api/memory/{index}/priority` | Set priority on an entry |
| `POST` | `/api/memory/touch` | Refresh access timestamp |
| `POST` | `/api/memory/boost` | Boost entry strength (+0.3) |
| `GET` | `/api/context` | Get assembled injection context |
| `GET` | `/api/recall` | Search memories and sessions |
| `GET` | `/api/briefing` | Generate task-specific briefing |
| `GET` | `/api/anchors` | Get environmental anchors |
| `POST` | `/api/consolidation` | Trigger consolidation |
| `GET` | `/api/consolidation/status` | Consolidation status |
| `GET` | `/api/costs/summary` | Cost analysis summary |
| `POST` | `/api/costs` | Record a cost observation |
| `GET` | `/api/procedures` | List procedures |
| `POST` | `/api/procedures` | Add a procedure |
| `POST` | `/api/procedures/search` | Search procedures |
| `POST` | `/api/procedures/outcome` | Record procedure outcome |
| `POST` | `/api/procedures/retire` | Retire a procedure |
| `GET` | `/api/decay/status` | Decay status |
| `POST` | `/api/reindex` | Backfill embeddings for a table |
| `POST` | `/api/context/smart` | Semantic dedup context injection |
| `GET` | `/dashboard` | Web dashboard |

### Vector Search & Embeddings (RAG)

pneural-context supports hybrid search combining traditional trigram/ILIKE text search with vector similarity search using pgvector. Results from both methods are merged using Reciprocal Rank Fusion (RRF).

**Setup:**

1. Install pgvector extension in PostgreSQL: `CREATE EXTENSION IF NOT EXISTS vector;`
2. Set `PNEURAL_EMBED_BACKEND=ollama` (default) and ensure Ollama is running with the embedding model pulled (`ollama pull nomic-embed-text`)
3. Embeddings are generated on-write when adding memory, consolidated, or procedural entries
4. Backfill existing entries: `POST /api/reindex` with `{"table": "all"}` or `{"table": "memory"}`

**New endpoints:**

- `GET /api/recall?project=X&q=Y&semantic=true` — hybrid recall (trigram + vector)
- `GET /api/context?project=X&semantic_query=Y` — hybrid context search
- `GET /api/procedures/search?project=X&q=Y&semantic=true` — hybrid procedure search
- `POST /api/context/smart` — semantic dedup context injection

**How it works:**

When `semantic=true` or `semantic_query` is provided, the server generates an embedding vector for the query, runs both trigram search and pgvector similarity search, then merges results using RRF (k=60). This produces better recall than either method alone — trigram catches exact matches, vector catches semantic similarity.

### Semantic Context Dedup

The `POST /api/context/smart` endpoint reduces context injection size by filtering entries that are semantically redundant with the current conversation.

**Three-zone filtering:**

| Similarity to conversation | Action | Reason |
|---|---|---|
| ≥ 0.85 (threshold_high) | **Skip** | Redundant — conversation already covers this |
| 0.55–0.85 | **Inject** | Relevant but not redundant — adds value |
| < 0.55 (threshold_low) | **Skip** | Irrelevant noise — not topically related |

Critical (red ink) entries with `strength ≥ 0.3` are **always injected** regardless of similarity, ensuring important context is never lost.

**Request:**

```json
{
  "project": "my-project",
  "conversation": "Last 10 messages from the conversation as text"
}
```

**Response:**

```json
{
  "project": "my-project",
  "source": "smart_dedup",
  "dedup_threshold_high": 0.85,
  "dedup_threshold_low": 0.55,
  "entries": [...]
}
```

## MCP Server

pneural-context includes an MCP (Model Context Protocol) server for integration with AI coding tools like opencode.

```bash
# Configure in opencode settings
PNEURAL_URL=http://localhost:8777
```

The MCP server exposes 22 tools for memory management, recall, consolidation, briefing, procedures, and cost tracking.

## Architecture

```
pneural_context/
├── pb_config.py       # Configuration (env vars, JSON)
├── pb_db.py           # PostgreSQL database layer (asyncpg)
├── pb_schema.sql      # Database schema (auto-applied)
├── pb_embeddings.py   # Embedding client (Ollama + Python backends)
├── pb_engine.py       # Core engine (consolidation, briefing, anchors, decay)
├── pb_llm.py          # LLM client (OpenAI-compatible)
├── pb_server.py        # FastAPI server with REST API + dashboard
├── pb_dashboard.py     # Inline HTML dashboard (no external dependencies)
├── pb_memoria.py       # Optional Memoria bridge (httpx)
└── cli.py              # Click CLI

mcp/
├── server.py           # MCP server (22 tools)
└── help_texts.py        # MCP tool descriptions
```

### Memory Tiers

Memories flow through three tiers:

1. **Immediate** — newly added entries, full detail
2. **Consolidated** — promoted by consolidation, compressed insights
3. **Timeless** — critical/core knowledge that never decays

### Memory Types

- **red** — critical always-present context (red ink)
- **concept** — domain knowledge and mental models
- **procedural** — step-by-step task patterns
- **temporal** — time-bound observations
- **relation** — connections between concepts

### Decay

Memory strength decays over time with configurable half-life. Entries below the archive threshold (default 0.1) are moved to the archive table. Archived entries remain searchable but are not injected into context by default.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PNEURAL_DATABASE_URL` | *(required)* | PostgreSQL connection string |
| `PNEURAL_LLM_URL` | `http://localhost:12345/v1` | OpenAI-compatible LLM endpoint |
| `PNEURAL_LLM_MODEL` | `local-model` | Model name for LLM calls |
| `PNEURAL_LLM_API_KEY` | *(empty)* | API key for LLM endpoint |
| `PNEURAL_HOST` | `0.0.0.0` | Server bind host |
| `PNEURAL_PORT` | `8777` | Server bind port |
| `PNEURAL_MEMORIA_URL` | *(empty)* | Memoria API URL for optional integration |
| `PNEURAL_MEMORIA_ENABLED` | `false` | Enable Memoria bridge |
| `PNEURAL_DECAY_INTERVAL` | `21600` | Decay loop interval (seconds) |
| `PNEURAL_CONSOLIDATION_INTERVAL` | `21600` | Consolidation loop interval (seconds) |
| `PNEURAL_ARCHIVE_THRESHOLD` | `0.1` | Strength threshold for archiving |
| `PNEURAL_EMBED_BACKEND` | `ollama` | Embedding backend (`ollama` or `python`) |
| `PNEURAL_EMBED_URL` | `http://localhost:11434` | Ollama API URL |
| `PNEURAL_EMBED_MODEL` | `nomic-embed-text` | Embedding model name |
| `PNEURAL_EMBED_DIMENSIONS` | `768` | Vector dimensions (must match model output) |
| `PNEURAL_EMBED_BATCH_SIZE` | `32` | Embedding batch size for reindex |
| `PNEURAL_DEDUP_THRESHOLD_HIGH` | `0.85` | Skip threshold (redundant with conversation) |
| `PNEURAL_DEDUP_THRESHOLD_LOW` | `0.55` | Filter threshold (irrelevant noise) |
| `PNEURAL_DEDUP_CONVERSATION_MESSAGES` | `10` | Number of recent messages for conversation embedding |

## Docker

```bash
docker build -t pneural-context .
docker run -e PNEURAL_DATABASE_URL=postgresql://user:pass@db:5432/pneural pneural-context
```

Or use docker-compose (see `examples/docker-compose.yml`):

```bash
docker compose up
```

## Database Schema

All tables use the `pb_` prefix for clean separation from other applications:

- `pb_memory` — memory entries with priority, type, strength, and timestamps
- `pb_procedural_memory` — captured task patterns with reinforcement scores
- `pb_consolidated_memory` — promoted consolidated insights
- `pb_memory_archive` — decayed entries below threshold
- `pb_memory_costs` — cost tracking per session
- `pb_papers` — optional paper/document references

## Optional: Memoria Integration

pneural-context works standalone. If you also run [Memoria](https://github.com/daivolt/memoria), enable the bridge:

```bash
export PNEURAL_MEMORIA_URL=http://localhost:8766
export PNEURAL_MEMORIA_ENABLED=true
```

This enriches consolidation and briefing with Memoria's session and topic data. Without Memoria, pneural-context uses its own memory entries directly.

## opencode Plugin

A plugin for [opencode](https://opencode.ai) that auto-injects pneural-context memory into every session and optionally records session summaries as memory entries.

### Features

- **Context injection** — fetches project memory on session start and injects it into the system prompt
- **Compaction preservation** — ensures pneural-context survives opencode's session compaction
- **Session recording** — on `session.idle`, summarizes the session in caveman style and stores it as a memory entry (opt-in)

### Setup

1. Copy the plugin file to your opencode plugins directory:

```bash
cp plugins/opencode/pneural-context.mjs ~/.config/opencode/plugins/
# or for project-level:
cp plugins/opencode/pneural-context.mjs .opencode/plugins/
```

2. Create a project mapping file in your project root:

```bash
echo '{"project": "my-project-name"}' > .pneural-context.json
```

3. Add `.pneural-context/` to your `.gitignore` (it stores cached context):

```
.pneural-context/
```

4. Set environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PNEURAL_CONTEXT_URL` | `http://localhost:8778` | pneural-context server URL |
| `PNEURAL_PROJECT` | *(from .pneural-context.json)* | Override project name |
| `PB_INJECT_ON_START` | `true` | Inject context on session start |
| `PB_INJECT_ON_COMPACT` | `true` | Preserve context through compaction |
| `PB_RECORD_SESSIONS` | `false` | Auto-record session summaries as memory |
| `PB_SESSION_RECORD_TYPE` | `temporal` | Memory type for recorded sessions (red, concept, procedural, temporal, relation) |
| `PB_SMART_DEDUP` | `false` | Enable semantic dedup for context injection |

### How it works

On every chat message, the plugin fetches your project's memory context from the pneural-context server (with a 5-minute cache) and injects it into the system prompt via `experimental.chat.system.transform`.

When opencode compacts a session, the plugin hooks into `experimental.session.compacting` to push a preservation instruction, ensuring the PNEURAL_CTX marker and pinned context survive the compaction.

When `PB_RECORD_SESSIONS=true`, the plugin waits for `session.idle` (agent finishes responding), fetches the session messages via the opencode SDK, and POSTs them to `POST /api/session/record`. The server uses its LLM to produce a caveman-style summary (ultra-compressed, technical, no fluff), then stores it as a temporal memory entry.

## License

AGPL-3.0-only — see [LICENSE](LICENSE).