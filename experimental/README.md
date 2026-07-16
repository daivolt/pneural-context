# pneural-context — Visual Architecture Guide

> Experimental visual documentation. These diagrams explain how the system works end-to-end.

## Quick Links

| Diagram | What It Shows |
|---------|--------------|
| [System Architecture](#1-system-architecture) | All components and their connections |
| [Injection Lifecycle](#2-injection-lifecycle) | How memories get injected into your LLM sessions |
| [RAG Pipeline](#3-rag-hybrid-search-pipeline) | How vector + trigram search finds relevant memories |
| [Smart Dedup Zones](#4-smart-dedup-zones) | Three-zone filtering to avoid redundant injection |
| [Memory Lifecycle](#5-memory-lifecycle) | From creation through decay to archive |
| [Consolidation Tiers](#6-consolidation-tiers) | How memories promote from immediate → timeless |
| [TurboQuant + RAG](#7-turboquant--rag-collaboration) | Which module does what — search vs reasoning |

---

## 1. System Architecture

The full stack: opencode client → plugin → pneural-context server → PostgreSQL + LLMs.

```mermaid
graph TB
    subgraph Client["Client Layer"]
        OC["opencode (CLI/TUI)"]
        Plugin["pneural-context plugin (index.mjs)"]
    end

    subgraph Server["pneural-context Server (port 8778)"]
        API["FastAPI REST API"]
        Engine["pb_engine.py (core logic)"]
        DB["pb_db.py (PostgreSQL + pgvector)"]
        LLM["pb_llm.py (LLM client)"]
        EMB["pb_embeddings.py (Ollama)"]
    end

    subgraph Storage["Storage Layer"]
        PG["PostgreSQL 16 + pgvector + pg_trgm"]
    end

    subgraph LLM_Layer["LLM Layer"]
        Ollama["Ollama (nomic-embed-text) port 11434"]
        TurboQuant["TurboQuant/llama.cpp (Qwen 2.5 Coder 7B) port 8080"]
    end

    OC -->|"chat events"| Plugin
    Plugin -->|"GET /api/context"| API
    Plugin -->|"POST /api/context/smart"| API
    Plugin -->|"POST /api/session/record"| API

    API --> Engine
    Engine --> DB
    Engine --> LLM
    Engine --> EMB

    DB --> PG
    EMB -->|"embed text"| Ollama
    LLM -->|"summarize/classify"| TurboQuant
```

### Component Roles

| Component | Role | Port |
|-----------|------|------|
| **opencode** | CLI/TUI client that the user interacts with | — |
| **pneural-context plugin** | Hooks into opencode events, injects context, records sessions | — |
| **pneural-context server** | FastAPI REST API — the brain of the system | 8778 |
| **PostgreSQL + pgvector** | Persistent storage with vector similarity search | 5432 |
| **Ollama (nomic-embed-text)** | Turns text into 768-dim vectors for semantic search | 11434 |
| **TurboQuant (Qwen 7B)** | LLM for summarization, classification, consolidation | 8080 |

---

## 2. Injection Lifecycle

How memories get into your LLM sessions at the right time.

```mermaid
sequenceDiagram
    participant User
    participant OC as opencode
    participant Plugin as pneural-context plugin
    participant Server as pneural-context (8778)
    participant DB as PostgreSQL

    Note over User,DB: Phase 1 — New Chat Session

    User->>OC: Start new chat
    OC->>Plugin: experimental.chat.system.transform
    Plugin->>Server: GET /api/context?project=X
    Server->>DB: SELECT memories WHERE project=X AND strength>=0.3
    DB-->>Server: memory entries
    Server-->>Plugin: markdown + PNEURAL_CTX marker
    Plugin->>OC: Inject context into system prompt
    OC->>User: Chat starts with memory context

    Note over User,DB: Phase 2 — Smart Dedup (with conversation)

    User->>OC: Send message
    OC->>Plugin: experimental.chat.system.transform
    Plugin->>OC: Collect last N messages
    Plugin->>Server: POST /api/context/smart {project, conversation}
    Server->>Server: Ollama embeds conversation
    Server->>DB: pgvector cosine search + trigram search
    Server->>Server: Three-zone filtering (skip/keep/always)
    Server-->>Plugin: deduplicated entries
    Plugin->>OC: Inject only relevant context

    Note over User,DB: Phase 3 — Session Recording

    OC->>Plugin: event: session.idle
    Plugin->>OC: Collect session messages
    Plugin->>Server: POST /api/session/record
    Server->>Server: TurboQuant summarizes session
    Server->>DB: INSERT summarized memory
    Server-->>Plugin: {id, summary, stored: true}

    Note over User,DB: Phase 4 — Compaction Preservation

    OC->>Plugin: experimental.session.compacting
    Plugin->>Server: GET /api/context?project=X
    Server-->>Plugin: PNEURAL_CTX marker
    Plugin->>OC: "Preserve PNEURAL_CTX marker verbatim"
    Note over OC: Summary keeps pinned context, drops old messages
```

### The Four Phases

1. **New Chat** — Plugin fetches all relevant memories and injects them as a system prompt block marked with `<!-- PNEURAL_CTX: xxxxxx -->`
2. **Smart Dedup** — When conversation exists, only inject memories not already covered. Uses embedding similarity to detect redundancy.
3. **Session Recording** — When a chat session goes idle, the LLM summarizes it into a compact memory entry stored for future recall.
4. **Compaction Preservation** — When opencode compacts the conversation (context overflow), the plugin ensures the PNEURAL_CTX block is preserved in the summary.

---

## 3. RAG Hybrid Search Pipeline

How pneural-context finds the right memories using both vector similarity and text matching.

```mermaid
flowchart LR
    Query["User Query"] --> Embed["Ollama embed (nomic-embed-text)"]
    Query --> Trigram["pg_trgm search (SQL LIKE + similarity)"]

    Embed --> VecSearch["pgvector cosine search (HNSW index)"]
    VecSearch --> RRF["RRF Score Fusion"]
    Trigram --> RRF

    RRF --> Filter{"Similarity > 0.55?"}
    Filter -->|"No: Irrelevant"| Skip["Skip"]
    Filter -->|"Yes"| Results["Ranked Results"]

    Results --> Dedup{"Smart Dedup (if conversation)"}
    Dedup -->|"Similarity > 0.85"| Already["Already in conversation — Skip"]
    Dedup -->|"0.55–0.85"| Inject["Inject into context"]
    Dedup -->|"Red Ink (critical)"| Always["Always inject"]
```

### Why Hybrid?

| Search Type | Good At | Bad At |
|------------|---------|--------|
| **pgvector (semantic)** | Conceptual matches ("deploy" ≈ "release") | Exact keyword matches |
| **pg_trgm (text)** | Typos, partial matches, exact terms | Can't find synonyms |
| **RRF Fusion** | Best of both — ranked by combined evidence | — |

Reciprocal Rank Fusion (RRF) combines both rankings:
```
score(memory) = 1/(k + rank_vector) + 1/(k + rank_trigram)
```

---

## 4. Smart Dedup Zones

When injecting context into a conversation, memories are filtered through three zones based on their similarity to what's already in the conversation.

```mermaid
graph LR
    subgraph Three_Zones["Smart Dedup — Three Zones"]
        direction TB
        Input["New memory or conversation message"]

        Input --> Calc["Calculate cosine similarity between memory and conversation"]

        Calc --> Zone1{"Similarity > 0.85?"}
        Zone1 -->|"Yes"| Skip["SKIP ZONE: Already covered in conversation text"]
        Zone1 -->|"No"| Zone2{"0.55 < Similarity < 0.85?"}

        Zone2 -->|"Yes"| Keep["KEEP ZONE: Relevant but not redundant — inject it"]
        Zone2 -->|"No"| Noise["NOISE ZONE: Irrelevant — skip"]

        Input --> Critical{"Is it Red Ink?"}
        Critical -->|"Yes (priority=critical)"| Always["ALWAYS INJECT: Regardless of similarity"]
    end
```

### Examples

| Zone | Similarity | Example | Action |
|------|-----------|---------|--------|
| **Skip** | > 0.85 | Memory: "Use git rebase for updates" / Conversation: "...git rebase for updates..." | Don't inject — user already knows |
| **Keep** | 0.55–0.85 | Memory: "Use env vars for secrets" / Conversation: "...CI pipeline setup..." | Inject — relevant new info |
| **Noise** | < 0.55 | Memory: "Meeting notes from Jan" / Conversation: "...deployment config..." | Don't inject — irrelevant |
| **Always** | Any | Memory: "NEVER commit secrets" (priority=critical) | Always inject, even if similar |

---

## 5. Memory Lifecycle

From creation through decay to archive — memories evolve over time.

```mermaid
flowchart TB
    Add["ADD MEMORY: POST /api/memory"]

    Add --> Embed["Ollama generates 768-dim embedding"]
    Embed --> Store["Store in pb_memory (entry + embedding + trigram index)"]

    Store --> Access["Memory accessed (context injection, recall)"]
    Access --> Boost["Boost strength +0.3 (spaced repetition)"]

    Store --> DecayClock["Time passes... strength decays via half-life formula"]

    DecayClock --> DecayRun{"Decay run: POST /api/decay"}

    DecayRun -->|"strength > 0.3"| Stable["Stable — remains in pb_memory"]
    DecayRun -->|"0.1 < strength < 0.3"| Fading["Fading — still injected, lower priority"]
    DecayRun -->|"strength < 0.1 (non-critical)"| Archive["Archive: POST /api/decay/archive"]

    Archive --> Archived["Moved to pb_memory_archive — forgotten but searchable"]

    Critical{"priority=critical?"}
    Add --> Critical
    Critical -->|"Yes"| RedInk["Red Ink — NEVER decays below 0.5, ALWAYS injected"]
    Critical -->|"No"| Normal["Normal — subject to decay lifecycle"]
```

### Key Concepts

- **Spaced Repetition**: Every time a memory is accessed (injected into context), its strength increases by +0.3 (capped at 1.0)
- **Decay**: Strength decays over time using a half-life formula. The default half-life is 7 days — after 7 days without access, strength drops to 50%
- **Archive**: Memories below 0.1 strength are moved to `pb_memory_archive`. They're "forgotten" but still searchable via `/api/recall`
- **Red Ink**: Critical-priority memories are protected. They never decay below 0.5 and are always injected regardless of dedup

---

## 6. Consolidation Tiers

Memories promote through three tiers as they're reinforced over time.

```mermaid
flowchart TB
    Input["New Memory Added"]

    Input --> Immediate["IMMEDIATE TIER: Raw episodic memory, short-lived, decays fast"]

    Immediate --> Consolidate{"Consolidation run: POST /api/consolidation"}

    Consolidate -->|"TurboQuant analyzes patterns"| Pattern["Pattern extraction by LLM"]

    Pattern --> Consolidated["CONSOLIDATED TIER: Extracted concepts, medium stability"]

    Consolidated -->|"Repeated reinforcement + high strength"| TimelessCheck{"Multiple reinforcements?"}
    TimelessCheck -->|"Yes"| Timeless["TIMELESS TIER: Core knowledge, never decays below 0.5, always injected"]
```

### Tier Properties

| Tier | Table | Half-life | Strength Floor | Auto-injected? |
|------|-------|-----------|---------------|----------------|
| **Immediate** | `pb_memory` | Hours–days | 0.0 (can decay to 0) | Yes, if strength > 0.3 |
| **Consolidated** | `pb_consolidated_memory` | Weeks–months | 0.3 | Yes |
| **Timeless** | `pb_consolidated_memory` (tier=timeless) | Never | 0.5 | Always |

### Promotion Logic

1. **Immediate → Consolidated**: TurboQuant groups related immediate memories and extracts a concept
2. **Consolidated → Timeless**: Memories with high reinforcement score (multiple successes) promote to timeless
3. **Red Ink stays in Immediate**: Critical-priority memories never leave `pb_memory` — they're always at full strength

---

## 7. TurboQuant + RAG Collaboration

The two LLM-backed modules serve completely different purposes. Understanding this division is key.

```mermaid
flowchart LR
    subgraph Problem["The Problem"]
        Direction["Which module does what?"]
    end

    subgraph Search["RAG Layer (Ollama + pgvector)"]
        Embed["nomic-embed-text: turns text into 768-dim vector"]
        VecSearch["pgvector cosine search: finds similar memories"]
        TriSearch["pg_trgm fuzzy search: finds partial text matches"]
        Fuse["RRF fusion: merges both rankings"]
    end

    subgraph Reasoning["Reasoning Layer (TurboQuant/Qwen)"]
        Summarize["Summarize sessions into memory entries"]
        Classify["Classify memory types (red/concept/procedural/...)"]
        Consolidate["Consolidate memories into higher tiers"]
        Brief["Generate briefing cards for task context"]
    end

    Direction --> Q1{"Need to FIND relevant memories?"}
    Q1 -->|"Yes"| Embed
    Embed --> VecSearch
    Embed --> TriSearch
    VecSearch --> Fuse
    TriSearch --> Fuse

    Direction --> Q2{"Need to UNDERSTAND or compress?"}
    Q2 -->|"Yes"| Summarize
    Q2 -->|"Yes"| Classify
    Q2 -->|"Yes"| Consolidate
    Q2 -->|"Yes"| Brief

    Fuse --> Result["Ranked relevant memories"]
    Summarize --> Result2["Compressed insights"]
    Classify --> Result2
    Consolidate --> Result2
    Brief --> Result2

    Result --> Inject["Injected into LLM context window"]
    Result2 --> Inject
```

### Division of Labor

| Task | Module | Why |
|------|--------|-----|
| Find memories similar to a query | **Ollama (RAG)** | Vector similarity is fast and exact |
| Find memories matching text fragments | **pg_trgm (RAG)** | Fuzzy text matching, no LLM needed |
| Merge vector + trigram results | **RRF (RAG)** | Pure math, no LLM needed |
| Decide if a memory is redundant | **Ollama (RAG)** | Embed similarity tells us overlap |
| Summarize a chat session | **TurboQuant (Reasoning)** | Needs language understanding |
| Classify a memory's type | **TurboQuant (Reasoning)** | Needs semantic comprehension |
| Consolidate memories into concepts | **TurboQuant (Reasoning)** | Needs abstraction ability |
| Generate a briefing card | **TurboQuant (Reasoning)** | Needs synthesis + prioritization |

### Cost Implications

| Module | When Called | Latency | Token Cost |
|--------|-----------|---------|------------|
| **Ollama (embed)** | Every write + every smart context request | ~50ms | 0 (local) |
| **TurboQuant (reasoning)** | Session record, consolidation, briefing, classify | ~2-5s | 0 (local) |

Both run locally — no API costs. TurboQuant is slower because it generates full text completions, while Ollama embedding is a single forward pass.

---

## API Quick Reference

| Endpoint | Method | Purpose | LLM Needed? |
|----------|--------|---------|-------------|
| `GET /health` | GET | Health check | No |
| `GET /api/memory` | GET | List memories | No |
| `POST /api/memory` | POST | Add memory | No (embed yes) |
| `GET /api/context` | GET | Get injected context | No |
| `POST /api/context/smart` | POST | Smart dedup context | Yes (embed) |
| `POST /api/recall` | GET | Semantic + trigram search | Yes (embed, if semantic=true) |
| `POST /api/session/record` | POST | Record + summarize session | Yes (TurboQuant) |
| `POST /api/consolidation` | POST | Run consolidation | Yes (TurboQuant) |
| `POST /api/decay` | POST | Run decay | No |
| `POST /api/decay/archive` | POST | Archive weak memories | No |
| `GET /api/decay/status` | GET | Check decay status | No |

---

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `PNEURAL_DATABASE_URL` | — | PostgreSQL connection string |
| `PNEURAL_LLM_URL` | `http://localhost:12345/v1` | LLM endpoint (TurboQuant) |
| `PNEURAL_LLM_MODEL` | `local-model` | LLM model name |
| `PNEURAL_PORT` | `8777` | Server port |
| `PNEURAL_EMBED_BACKEND` | `ollama` | Embedding backend (ollama or python) |
| `PNEURAL_EMBED_URL` | `http://localhost:11434` | Ollama URL |
| `PNEURAL_EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `PNEURAL_EMBED_DIMENSIONS` | `768` | Vector dimensions |
| `PNEURAL_DEDUP_THRESHOLD_HIGH` | `0.85` | Skip zone threshold |
| `PNEURAL_DEDUP_THRESHOLD_LOW` | `0.55` | Noise zone threshold |
