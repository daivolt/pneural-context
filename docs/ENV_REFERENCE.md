# Environment Variable Reference

## Required

| Variable | Default | Description |
|----------|---------|-------------|
| `PNEURAL_DATABASE_URL` | — | PostgreSQL connection string |

## Server

| Variable | Default | Description |
|----------|---------|-------------|
| `PNEURAL_HOST` | `127.0.0.1` | Bind address |
| `PNEURAL_PORT` | `8778` | Listen port |
| `PNEURAL_LOG_LEVEL` | `INFO` | Logging level |

## LLM / Turboquant

| Variable | Default | Description |
|----------|---------|-------------|
| `PNEURAL_LLM_URL` | `http://localhost:12345/v1` | OpenAI-compatible LLM API URL |
| `PNEURAL_LLM_MODEL` | — | Model name string |
| `PNEURAL_LLM_API_KEY` | — | API key if required |
| `PNEURAL_LLM_LAUNCH_CMD` | — | Command to auto-start LLM at server boot |

## Embeddings

| Variable | Default | Description |
|----------|---------|-------------|
| `PNEURAL_EMBED_BACKEND` | `ollama` | `ollama` or `sentence_transformers` |
| `PNEURAL_EMBED_URL` | `http://localhost:11434` | Ollama API URL |
| `PNEURAL_EMBED_MODEL` | `nomic-embed-text` | Embedding model name |
| `PNEURAL_EMBED_DIMENSIONS` | `768` | Embedding vector dimensions |

## Decay & Consolidation

| Variable | Default | Description |
|----------|---------|-------------|
| `PNEURAL_DECAY_INTERVAL` | `21600` | Decay cycle in seconds (0=off) |
| `PNEURAL_CONSOLIDATION_INTERVAL` | `21600` | Consolidation cycle in seconds (0=off) |
| `PNEURAL_ARCHIVE_THRESHOLD` | `0.1` | Strength below which entries are archived |

## Context Injection

| Variable | Default | Description |
|----------|---------|-------------|
| `PNEURAL_CONTEXT_MAX_ENTRIES` | `20` | Max entries in assembled context |
| `PNEURAL_CONTEXT_MAX_TOKENS` | `4000` | Token budget for context |
| `PNEURAL_ANCHORS_LIMIT` | `5` | Max anchors in context |
| `PNEURAL_MAX_SEARCH_RESULTS` | `50` | Max FTS results |

## Memoria Integration

| Variable | Default | Description |
|----------|---------|-------------|
| `PNEURAL_MEMORIA_ENABLED` | `false` | Enable Memoria bridge |
| `PNEURAL_MEMORIA_URL` | — | Memoria MCP server URL |

## Plugin (opencode)

| Variable | Default | Description |
|----------|---------|-------------|
| `PNEURAL_CONTEXT_URL` | `http://localhost:8778` | pneural-context API URL |
| `PB_INJECT_ON_START` | `true` | Inject context on session start |
| `PB_INJECT_ON_COMPACT` | `true` | Preserve markers during compaction |
| `PB_RECORD_SESSIONS` | `false` | Record sessions to pb_memory |
| `PB_SESSION_RECORD_TYPE` | `temporal` | Memory type for session records |
| `PB_SMART_DEDUP` | `true` | Use conversation history for dedup |
| `PB_DEDUP_MESSAGES` | `10` | Recent messages to use for dedup |
