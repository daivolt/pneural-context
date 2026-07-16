# pneural-context

> **EXPERIMENTAL ALPHA — UNDER CONSTRUCTION**
>
> APIs will change without notice. Data schemas may be incompatible between versions.
> No migration paths are guaranteed. Use at your own risk.

Persistent neural context layer for LLM agents — memory, consolidation, decay, and recall.

LLMs have anterograde amnesia: every session starts from scratch, and context compaction loses information the way anterograde amnesia destroys continuity. pneural-context stores, consolidates, decays, and recalls context so an agent can recover relevant memory at the start of a new session.

## Why

Give LLM agents a durable memory layer that outlives session death — so work done in one session is recoverable in the next.

## Inspired By

- **Junko Mizuta** — a Japanese woman who, after herpes simplex virus damaged her brain, was left with approximately 7 seconds of short-term memory. She carried a blue notebook everywhere, writing down what she did, who she spoke to, and where she went. Over time the volume of notebooks became unmanageable; when moving in with relatives, she shredded months of her own notes. She eventually stopped taking memos entirely. This paradox — notes as both lifeline and burden, the choice to stop writing rather than drown in paper — directly motivated our design: pneural-context has a consolidation pipeline (to prevent unmanageable volume) and graceful forgetting via Ebbinghaus decay (accepting that not everything needs to be kept, as Mizuta herself demonstrated when she stopped writing). — *CBC Documentary: Ever Vanishing Present* (dir. Toshihiro Matsumoto, 2017)

- **Clive Wearing** — a British musician who lost the ability to form new declarative memories after herpes simplex viral encephalitis in 1985, living in an eternal present with a ~7-30 second memory span. He filled diary after diary with entries like "8:31 AM: Now I am really, completely awake" — then crossed them out moments later, unable to recognize his own handwriting. Despite catastrophic amnesia, his procedural memory (conducting, playing piano) and emotional responses remained intact. This dissociation between destroyed declarative memory and preserved procedural/emotional memory directly motivated our separation of memory into five types (`red`, `concept`, `procedural`, `temporal`, `relation`) and our decision to give procedural entries higher decay resistance.

- **Hippocampal replay** — during slow-wave sleep, hippocampal place cells reactivate in the same sequences as during waking experience (Wilson & McNaughton, 1994), transferring short-term traces to neocortical long-term storage. Our 3-tier consolidation pipeline (`immediate → consolidated → timeless`) directly mirrors this hippocampo-neocortical transfer.

- **Ebbinghaus forgetting curve** — memory decays exponentially unless refreshed through recall (Ebbinghaus, 1885/1913). Our decay system applies `strength *= 0.95` per consolidation cycle, and `boost_entry` adds `+0.3` strength on access (capped at 1.0) — a computational implementation of spaced repetition.

### Scientific References

1. Ebbinghaus, H. (1913). *Memory: A contribution to experimental psychology*. New York: Teachers College, Columbia University.
2. Murre, J. M. J., & Dros, J. (2015). Replication and analysis of Ebbinghaus' forgetting curve. *PLOS ONE*, 10(7), e0120644.
3. Buzsáki, G. (1996). The hippocampo-neocortical dialogue. *Cerebral Cortex*, 6(2), 81–92.
4. Diekelmann, S., & Born, J. (2010). The memory function of sleep. *Nature Reviews Neuroscience*, 11(2), 114–126.
5. Cepeda, N. J., et al. (2006). Distributed practice in verbal recall tasks. *Psychological Bulletin*, 132(3), 354–380.
6. Wilson, M. A., & McNaughton, B. L. (1994). Reactivation of hippocampal ensemble memories during sleep. *Science*, 265(5172), 676–679.
7. Wilson, B. A., Baddeley, A. D., & Kapur, N. (1995). Dense amnesia in a professional musician following herpes simplex virus encephalitis. *Journal of Clinical and Experimental Neuropsychology*, 17(5), 668–681.

---

## Features

- **Memory entries** with priority levels (critical/important/normal) and typed classification (red/concept/procedural/temporal/relation)
- **Automatic consolidation** that promotes frequently-accessed memories to higher tiers and archives forgotten ones
- **Spaced repetition** via boost/touch operations that strengthen memories before they decay
- **Ebbinghaus decay** that gradually reduces memory strength over time, archiving entries below threshold
- **Briefing cards** that assemble relevant context for a specific task
- **Procedural memory** that captures recurring task patterns and their outcomes
- **Cost tracking** for monitoring context injection efficiency
- **Hybrid search** (trigram + vector with RRF fusion) for recall
- **Semantic context dedup** — three-zone filtering to reduce redundant context injection
- **MCP server** with 22 tools for AI coding tool integration
- **opencode plugin** for automatic context injection and session recording
- **Web dashboard** for monitoring memory state (inline HTML, no external dependencies)

## Requirements

- Python 3.11+
- PostgreSQL 14+ with extensions: `pg_trgm`, `uuid-ossp`, `pgvector`
- An OpenAI-compatible LLM endpoint (LM Studio, Ollama, llama.cpp server, OpenAI, etc.)
- Ollama (for embeddings, default backend)

## Install

```bash
git clone https://github.com/daivolt/pneural-context.git
cd pneural-context
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e .
```

Optional dependencies:

```bash
# Memoria integration
pip install -e ".[memoria]"

# Python-based embeddings (alternative to Ollama)
pip install -e ".[embeddings]"

# Development
pip install -e ".[dev]"
```

## Quick Start

### 1. Create the database

```sql
CREATE DATABASE pneural;
CREATE USER pneural WITH PASSWORD 'pneural_dev';
GRANT ALL PRIVILEGES ON DATABASE pneural TO pneural;

-- Connect to the pneural database, then:
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
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

# Search memories (text only)
curl "http://localhost:8777/api/recall?project=my-project&q=insight"

# Search memories (hybrid: text + vector)
curl "http://localhost:8777/api/recall?project=my-project&q=insight&semantic=true"

# Generate a briefing for a task
curl "http://localhost:8777/api/briefing?project=my-project&task=implement+auth+system"

# Trigger consolidation
curl -X POST http://localhost:8777/api/consolidation \
  -H "Content-Type: application/json" \
  -d '{"project": "my-project"}'

# Semantic context dedup
curl -X POST http://localhost:8777/api/context/smart \
  -H "Content-Type: application/json" \
  -d '{"project": "my-project", "conversation": "Last 10 messages from the conversation as text"}'
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

# Classify all memory entries by type
pneural-context classify -p my-project

# Backfill embeddings for existing entries
pneural-context reindex -p my-project
```

## REST API

All endpoints use the `/api/` prefix.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/memory` | Add a memory entry |
| `GET` | `/api/memory` | List memory entries |
| `GET` | `/api/memory/full` | List entries with full metadata |
| `GET` | `/api/memory/red-ink` | Get critical (red ink) entries |
| `GET` | `/api/memory/type/{type}` | Get entries by memory type |
| `PATCH` | `/api/memory/{id}/priority` | Set priority on an entry |
| `PATCH` | `/api/memory/{id}/type` | Set memory type on an entry |
| `DELETE` | `/api/memory/{id}` | Delete a memory entry |
| `POST` | `/api/memory/replace` | Replace a memory entry (find/replace text) |
| `POST` | `/api/memory/touch` | Refresh access timestamp |
| `POST` | `/api/memory/boost` | Boost entry strength (+0.3) |
| `POST` | `/api/memory/classify` | Auto-classify all entries by type |
| `GET` | `/api/context` | Get assembled injection context |
| `POST` | `/api/context/smart` | Semantic dedup context injection |
| `GET` | `/api/recall` | Search memories (text or hybrid) |
| `GET` | `/api/briefing` | Generate task-specific briefing |
| `GET` | `/api/anchors` | Get environmental anchors |
| `POST` | `/api/consolidation` | Trigger consolidation |
| `GET` | `/api/consolidation/status` | Consolidation status |
| `GET` | `/api/decay/status` | Decay status |
| `POST` | `/api/decay` | Trigger decay cycle |
| `POST` | `/api/decay/archive` | Trigger decay + archive |
| `GET` | `/api/archive/search` | Search archived entries |
| `POST` | `/api/procedures` | Add a procedure |
| `GET` | `/api/procedures` | List procedures |
| `GET` | `/api/procedures/search` | Search procedures |
| `POST` | `/api/procedures/{id}/outcome` | Record procedure outcome |
| `POST` | `/api/procedures/{id}/retire` | Retire a procedure |
| `GET` | `/api/costs/summary` | Cost analysis summary |
| `POST` | `/api/costs` | Record a cost observation |
| `GET` | `/api/costs/trends` | Cost trend data |
| `POST` | `/api/reindex` | Backfill embeddings for a table |
| `POST` | `/api/session/record` | Record a session as a memory entry |
| `GET` | `/api/projects` | List all projects |
| `GET` | `/api/config` | Get current configuration |
| `PATCH` | `/api/config` | Update configuration |
| `GET` | `/dashboard` | Web dashboard |
| `GET` | `/health` | Health check |

## Vector Search & Embeddings (RAG)

pneural-context supports hybrid search combining traditional trigram/ILIKE text search with vector similarity search using pgvector. Results from both methods are merged using Reciprocal Rank Fusion (RRF).

### Setup

1. Install the pgvector extension in PostgreSQL: `CREATE EXTENSION IF NOT EXISTS vector;`
2. Set `PNEURAL_EMBED_BACKEND=ollama` (default) and ensure Ollama is running with the embedding model pulled:
   ```bash
   ollama pull nomic-embed-text
   ```
3. Embeddings are generated on-write when adding memory, consolidated, or procedural entries
4. Backfill existing entries: `POST /api/reindex` with `{"table": "all"}` or `{"table": "memory"}`

### Hybrid Search

- `GET /api/recall?project=X&q=Y&semantic=true` — hybrid recall (trigram + vector)
- `GET /api/context?project=X&semantic_query=Y` — hybrid context search
- `GET /api/procedures/search?project=X&q=Y&semantic=true` — hybrid procedure search

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

The MCP server exposes 22 tools for memory management, recall, consolidation, briefing, procedures, and cost tracking. See `mcp/server.py` for the full tool list.

## opencode Plugin

A plugin for [opencode](https://opencode.ai) that auto-injects pneural-context memory into every session and optionally records session summaries as memory entries.

### Features

- **Context injection** — fetches project memory on session start and injects it into the system prompt via `experimental.chat.system.transform`
- **Compaction preservation** — ensures pneural-context survives opencode's session compaction via `experimental.session.compacting`
- **Semantic dedup** — reduces redundant context by comparing memory entries against the current conversation
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

3. Add `.pneural-context/` to your `.gitignore` (it stores cached context).

4. Set environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PNEURAL_CONTEXT_URL` | `http://localhost:8778` | pneural-context server URL |
| `PNEURAL_PROJECT` | *(from .pneural-context.json)* | Override project name |
| `PB_INJECT_ON_START` | `true` | Inject context on session start |
| `PB_INJECT_ON_COMPACT` | `true` | Preserve context through compaction |
| `PB_RECORD_SESSIONS` | `false` | Auto-record session summaries as memory |
| `PB_SESSION_RECORD_TYPE` | `temporal` | Memory type for recorded sessions |
| `PB_SMART_DEDUP` | `false` | Enable semantic dedup for context injection |

### How it works

On every chat message, the plugin fetches your project's memory context from the pneural-context server (with a 5-minute cache) and injects it into the system prompt.

When opencode compacts a session, the plugin hooks into `experimental.session.compacting` to push a preservation instruction, ensuring the PNEURAL_CTX marker and pinned context survive the compaction.

When `PB_RECORD_SESSIONS=true`, the plugin waits for `session.idle` (agent finishes responding), fetches the session messages via the opencode SDK, and POSTs them to `POST /api/session/record`. The server uses its LLM to produce a caveman-style summary (ultra-compressed, technical, no fluff), then stores it as a temporal memory entry.

## LLM Backend

pneural-context uses an OpenAI-compatible LLM API for consolidation, briefing generation, session summarization, and memory classification. Any server that implements the `/v1/chat/completions` endpoint works:

| Backend | `PNEURAL_LLM_URL` | `PNEURAL_LLM_MODEL` | Notes |
|---------|-------------------|---------------------|-------|
| LM Studio | `http://localhost:1234/v1` | model name from LM Studio | Default port 1234 |
| Ollama | `http://localhost:11434/v1` | `llama3` or any pulled model | Needs `/v1` suffix |
| llama.cpp server | `http://localhost:8080/v1` | model filename or `default` | Supports KV cache quantization |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` etc. | Set `PNEURAL_LLM_API_KEY` |
| Any OpenAI-compatible | endpoint URL | model identifier | Must support chat completions |

### KV Cache Quantization with llama.cpp

For local inference on consumer hardware, [llama.cpp](https://github.com/ggerganov/llama.cpp) supports KV cache quantization to dramatically reduce memory usage for long contexts:

```bash
# Standard: ~2x context in same VRAM
llama-server -m model.gguf -ngl 99 -ctk q8_0 -ctv q8_0 --port 8080

# TurboQuant: ~3x context compression
llama-server -m model.gguf -ngl 99 -ctk q8_0 -ctv turbo4 --port 8080
```

- **`-ctk q8_0`** — quantize key cache to 8-bit (halves key cache memory)
- **`-ctv q8_0`** — quantize value cache to 8-bit (halves value cache memory)
- **`-ctv turbo4`** — TurboQuant 4-bit value cache (~3x total KV cache compression, Vulkan-compatible via [TheTom/llama-cpp-turboquant](https://github.com/TheTom/llama-cpp-turboquant))

This allows running 7B parameter models with 32K+ context on 12GB GPUs that would otherwise OOM.

## Architecture

```
pneural_context/
├── pb_config.py       # Configuration (env vars, JSON)
├── pb_db.py           # PostgreSQL database layer (asyncpg + pgvector)
├── pb_schema.sql      # Database schema (auto-applied)
├── pb_embeddings.py   # Embedding client (Ollama + Python backends)
├── pb_engine.py       # Core engine (consolidation, briefing, anchors, decay)
├── pb_llm.py          # LLM client (OpenAI-compatible)
├── pb_server.py       # FastAPI server with REST API + dashboard
├── pb_dashboard.py    # Inline HTML dashboard (no external dependencies)
├── pb_memoria.py      # Optional Memoria bridge (httpx)
└── cli.py             # Click CLI

mcp/
├── server.py          # MCP server (22 tools)
└── help_texts.py      # MCP tool descriptions

plugins/opencode/
└── pneural-context.mjs  # opencode plugin
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

Critical (red ink) entries never decay below `strength = 0.5`.

## Configuration

All configuration is via environment variables or the `.env` file. No secrets are hardcoded — everything comes from the environment.

| Variable | Default | Description |
|----------|---------|-------------|
| `PNEURAL_DATABASE_URL` | *(required)* | PostgreSQL connection string |
| `PNEURAL_LLM_URL` | `http://localhost:12345/v1` | OpenAI-compatible LLM endpoint |
| `PNEURAL_LLM_MODEL` | `local-model` | Model name for LLM calls |
| `PNEURAL_LLM_API_KEY` | *(empty)* | API key for LLM endpoint (if required) |
| `PNEURAL_HOST` | `0.0.0.0` | Server bind host |
| `PNEURAL_PORT` | `8777` | Server bind port |
| `PNEURAL_MEMORIA_URL` | *(empty)* | Memoria API URL for optional integration |
| `PNEURAL_MEMORIA_ENABLED` | `false` | Enable Memoria bridge |
| `PNEURAL_DECAY_INTERVAL` | `21600` | Decay loop interval in seconds (6 hours) |
| `PNEURAL_CONSOLIDATION_INTERVAL` | `21600` | Consolidation loop interval in seconds |
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

- `pb_memory` — memory entries with priority, type, strength, vector embeddings, and timestamps
- `pb_procedural_memory` — captured task patterns with reinforcement scores and vector embeddings
- `pb_consolidated_memory` — promoted consolidated insights with tier, vector embeddings
- `pb_memory_archive` — decayed entries below threshold
- `pb_memory_costs` — cost tracking per session
- `pb_papers` — optional paper/document references

The schema is auto-applied on first startup. Vector columns use pgvector's `vector(768)` type (configurable via `PNEURAL_EMBED_DIMENSIONS`).

## Optional: Memoria Integration

pneural-context works standalone. If you also run [Memoria](https://github.com/daivolt/memoria), enable the bridge:

```bash
export PNEURAL_MEMORIA_URL=http://localhost:8766
export PNEURAL_MEMORIA_ENABLED=true
```

This enriches consolidation and briefing with Memoria's session and topic data. Without Memoria, pneural-context uses its own memory entries directly.

## Standalone Usage (Python)

```python
import asyncio
from pneural_context.pb_config import PBConfig
from pneural_context.pb_db import init_pool, add_memory_entry, get_memory_entries
import asyncpg

async def main():
    config = PBConfig.from_env()
    pool = await asyncpg.create_pool(config.database_url, min_size=2, max_size=10)
    init_pool(pool)

    entry_id = await add_memory_entry("demo", "Always use pb_ prefix for tables", "critical")
    print(f"Added entry: {entry_id}")

    entries = await get_memory_entries("demo")
    for e in entries:
        print(f"  [{e['id']}] {e['entry']}")

    await pool.close()

asyncio.run(main())
```

## License

AGPL-3.0-only — see [LICENSE](LICENSE).