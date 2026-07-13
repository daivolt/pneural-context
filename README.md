# pneural-context

> **⚠️ EXPERIMENTAL ALPHA — DO NOT USE IN PRODUCTION**
>
> This software is in early alpha. APIs will change without notice. Things will break.
> Data schemas may be incompatible between versions. No migration paths are guaranteed.

Persistent neural context for LLMs — memory, consolidation, decay, and recall.

pneural-context gives LLM agents a durable memory that outlives session death. Inspired by how human memory consolidates experiences during sleep and decays unused information over time, it provides:

- **Memory entries** with priority levels (critical/important/normal) and typed classification (red/concept/procedural/temporal/relation)
- **Automatic consolidation** that promotes frequently-accessed memories to higher tiers and archives forgotten ones
- **Spaced repetition** via boost/touch operations that strengthen memories before they decay
- **Decay** that gradually reduces memory strength over time, archiving entries below a threshold
- **Briefing cards** that assemble relevant context for a specific task
- **Procedural memory** that captures recurring task patterns and their outcomes
- **Cost tracking** for monitoring context injection efficiency

## Requirements

- Python 3.11+
- PostgreSQL 14+ (with `pg_trgm` and `uuid-ossp` extensions)
- An OpenAI-compatible LLM endpoint (LM Studio, Ollama, OpenAI, etc.)

## Install

```bash
pip install pneural-context
```

For optional Memoria integration:

```bash
pip install pneural-context[memoria]
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
| `GET` | `/api/recall` | Search memories with LLM enrichment |
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
| `GET` | `/dashboard` | Web dashboard |

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

## Inspired By

- **Junko Mizuta's "paper brain" notebook system** — a physical organizational method for researchers to manage papers, notes, and ideas using structured index cards
- **Clive Wearing's condition** — a musician who lost the ability to form new memories, living in an eternal present, reminding us why persistent context beyond the moment matters
- **Hippocampal replay** — the neuroscience of how the brain consolidates experiences during sleep, promoting short-term traces into long-term knowledge

## License

AGPL-3.0-only — see [LICENSE](LICENSE).