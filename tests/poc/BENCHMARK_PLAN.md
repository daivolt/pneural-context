# Pneural-Context End-to-End PoC Benchmark Plan

## What This Is

A **Proof of Concept** — not a unit test suite, not a benchmark competition. A steel-thread demonstration that proves the full system works end-to-end: from memory seeding through context injection into a real LLM, through compaction survival, session recording, and every API feature.

Per academic research (RAGAS arXiv:2309.15217, LLM-as-a-Judge NeurIPS 2023, AgentBench ICLR 2024):

- **PoC** = prove feasibility with a real scenario, explicit success criteria, control vs treatment comparison
- **Test suite** = verify individual code paths pass/fail (what the existing 52 tests do)
- **Benchmark** = standardized tasks with numerical scores for ranking systems

This PoC has a **control arm** (plugin disabled) and a **treatment arm** (plugin enabled) running the same real conversation, with three inspection layers verifying the full chain.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    BENCHMARK HARNESS                              │
│                                                                  │
│  1. SEED MEMORY (all 5 types, all 3 priorities)                 │
│     ↓                                                            │
│  2. CONTROL ARM — opencode with plugin disabled (dead port)      │
│     ├── 10-turn real conversation building FastAPI task API      │
│     ├── llama.cpp logs captured (--log-prompt)                   │
│     ├── opencode SQLite DB captured (session_message table)      │
│     └── Response + token data saved per turn                     │
│     ↓                                                            │
│  3. TREATMENT ARM — opencode with plugin enabled (port 8779)     │
│     ├── Same 10-turn conversation, same temperature=0            │
│     ├── llama.cpp logs captured                                  │
│     ├── opencode SQLite DB captured                              │
│     ├── Triggers: injection, smart dedup, compaction, recording │
│     └── Response + token data saved per turn                    │
│     ↓                                                            │
│  4. POST-CONVERSATION API EXERCISES                              │
│     ├── Consolidation → verify tiers                             │
│     ├── Decay (3x) → verify red ink floor at 0.5               │
│     ├── Archive → verify sub-0.1 entries archived              │
│     ├── Archive search → verify searchable                      │
│     ├── Procedures → add, search, outcomes, auto-retire        │
│     ├── Briefing → verify LLM-generated structured output      │
│     ├── Anchors → verify distributions                          │
│     ├── Cost analysis → record, summary, trends                 │
│     ├── Recall (trigram + semantic) → verify boost              │
│     ├── Smart dedup → 3 zone behaviors + red ink always          │
│     ├── Full context → markdown with all sections               │
│     ├── MCP subprocess → all 29 tools                           │
│     ├── MCP feature toggle → disable PB_MEMORY                 │
│     ├── Session recording → verify temporal entry               │
│     ├── Auto-classify → verify type reassignment               │
│     ├── Config hot-reload → PATCH /api/config                   │
│     ├── Projects list → GET /api/projects                       │
│     ├── Reindex → POST /api/reindex                              │
│     └── Dashboard → GET /dashboard                               │
│     ↓                                                            │
│  5. EVALUATION                                                   │
│     ├── PNEURAL_CTX marker in treatment logs (binary)            │
│     ├── PNEURAL_CTX absent in control logs (binary)              │
│     ├── Marker survival in compaction (SQLite DB)               │
│     ├── Session recording verification (temporal entry exists)   │
│     ├── Faithfulness: treatment references seeded facts         │
│     ├── Pairwise LLM judge (DeepSeek Flash, position-swapped)   │
│     ├── Token cost comparison (control vs treatment)            │
│     └── Code quality: run the tests the LLM wrote               │
│     ↓                                                            │
│  6. REPORT — structured JSON, reproducible, comparable          │
└──────────────────────────────────────────────────────────────────┘
```

## The App: FastAPI Task Management API

The opencode session will build a real application during the benchmark conversation. This naturally exercises all memory types:

- Architecture decisions → **concept** memory
- Coding conventions → **procedural** memory
- Security rules → **red ink** memory
- Entity relationships → **relation** memory
- Session history → **temporal** memory

## Memory Seed Data (8 entries — all 5 types, all 3 priorities)

| # | Type | Priority | Content |
|---|------|----------|---------|
| 1 | red | critical | "Never hardcode database credentials — always use environment variables with os.environ.get() and fail fast if missing" |
| 2 | red | critical | "Always validate input with Pydantic models before any database operations — reject invalid data with 422 status" |
| 3 | concept | important | "This project uses FastAPI with asyncpg for PostgreSQL access — use connection pooling with min_size=2, max_size=10" |
| 4 | concept | important | "The project follows Bloomberg engineering standards: full type hints, fail-fast on missing env vars, generic error messages in production, detailed errors only in dev" |
| 5 | procedural | normal | "To add a new endpoint: 1) Create Pydantic request/response models in models/, 2) Write the router in routers/, 3) Register in server.py with app.include_router(), 4) Add tests in tests/ using httpx.AsyncClient" |
| 6 | procedural | normal | "Tests use pytest with httpx.AsyncClient and pytest-asyncio. Run with: pytest tests/ -v -m 'not integration'. Coverage gate at 70%." |
| 7 | temporal | normal | "Previous session: user designed a task management API with CRUD endpoints and asked for pagination with limit/offset" |
| 8 | relation | normal | "Task model has a many-to-one relationship with User model via foreign key user_id — tasks belong to users" |

## Conversation Script (10 turns, fixed)

```json
[
  "I want to build a task management API with FastAPI and asyncpg. Help me design the architecture.",
  "Create the Pydantic models for Task and User with proper type hints.",
  "Write the database connection layer using asyncpg connection pooling.",
  "Add CRUD endpoints for tasks with proper HTTP status codes.",
  "Add error handling — validate all inputs, return 422 for bad data.",
  "Write pytest tests for the CRUD endpoints using httpx async client.",
  "Add API key authentication middleware for protected endpoints.",
  "Refactor to use the repository pattern — separate data access from routes.",
  "Add pagination to the list endpoint with limit and offset query parameters.",
  "Write a docker-compose.yml for local development with PostgreSQL."
]
```

Why 10 turns:
- References seeded memory directly (asyncpg, FastAPI, Pydantic, Bloomberg standards, env vars, repository pattern, httpx.AsyncClient, user_id, pagination)
- Long enough to fill context window → trigger compaction
- Produces real runnable code we can test

## Control vs Treatment

| | Control (Arm A) | Treatment (Arm B) |
|---|---|---|
| Plugin | Disabled (PNEURAL_CONTEXT_URL=http://localhost:9999) | Enabled (PNEURAL_CONTEXT_URL=http://localhost:8779) |
| Model | qwen2.5-coder-7b-instruct | Same |
| Temperature | 0 | 0 |
| Prompts | Same 10 prompts | Same 10 prompts |
| PB_RECORD_SESSIONS | false | true |
| PB_SMART_DEDUP | false | true |
| PB_INJECT_ON_START | false | true |
| PB_INJECT_ON_COMPACT | false | true |
| LLM logs | --log-prompt | --log-prompt |

## Three Inspection Layers

### Layer 1: llama.cpp Logs

Restart llama-server with `--log-prompt` flag. This writes the full prompt (including system prompt) to stderr.

- `treatment_llama.log` — grep for `PNEURAL_CTX` → must be present
- `control_llama.log` — grep for `PNEURAL_CTX` → must be absent
- Also extract: system prompt content, total input tokens per request, whether injected memory entries appear verbatim

### Layer 2: opencode SQLite DB

Path on ryzen: `C:\Users\daivolt\AppData\Local\opencode\opencode.db`

Queries:
```sql
-- Compaction messages (verify PNEURAL_CTX survives)
SELECT id, type, seq, data FROM session_message
WHERE session_id = ? AND type = 'compaction' ORDER BY seq;

-- System messages (context injection evidence)
SELECT id, type, seq, data FROM session_message
WHERE session_id = ? AND type = 'system' ORDER BY seq;

-- All messages for the session
SELECT id, type, seq, time_created FROM session_message
WHERE session_id = ? ORDER BY seq;
```

Treatment must show PNEURAL_CTX in compaction summary. Control must not.

### Layer 3: Response Content Analysis (Faithfulness)

For each turn, check if the response references seeded facts:

| Seed ID | Search Terms | Type |
|---------|-------------|------|
| #1 (red ink) | "environment variables", "os.environ", "fail fast", "credentials" | Security |
| #2 (red ink) | "Pydantic", "validate", "422" | Validation |
| #3 (concept) | "asyncpg", "connection pool", "min_size" | Tech stack |
| #4 (concept) | "Bloomberg", "type hints", "fail-fast", "generic error" | Standards |
| #5 (procedural) | "include_router", "models/", "routers/", "httpx.AsyncClient" | Process |
| #6 (procedural) | "pytest", "httpx", "AsyncClient", "pytest-asyncio" | Testing |
| #7 (temporal) | "pagination", "limit", "offset" | Context |
| #8 (relation) | "user_id", "foreign key", "many-to-one" | Data model |

Score per turn = matched facts / 8. Treatment should score significantly higher.

## Pairwise LLM-as-a-Judge (DeepSeek Flash Free)

For each of the 10 turns, run 2 comparisons (position-swapped to eliminate bias):

**Comparison 1:** A=control response, B=treatment response
**Comparison 2:** A=treatment response, B=control response

Judge prompt (blind, no labels):
```
You are evaluating two AI assistant responses to the same coding prompt.

Prompt: "<the user's message>"

Response A:
<response_a>

Response B:
<response_b>

Which response is better? Consider:
1. Correctness — does the code work?
2. Convention adherence — does it follow established patterns?
3. Security — does it handle secrets and validation properly?
4. Completeness — does it address all parts of the request?
5. Code quality — is it clean, typed, well-structured?

Respond with ONLY one of: "A", "B", or "TIE"
```

If position-swapped comparisons agree → strong signal. If they disagree → position bias detected, mark as inconclusive.

Implementation: DeepSeek Flash free tier via `https://api.deepseek.com/v1/chat/completions`, model `deepseek-chat`.

Win rate = treatment wins / total comparisons (excluding ties and inconclusive).

## Post-Conversation API Exercises

After both arms complete, exercise every pneural-context feature:

| # | Feature | How | What to verify |
|---|---------|-----|-----------------|
| 1 | Consolidation | `POST /api/consolidation` | immediate_created > 0, insights_created > 0, critical promoted to timeless |
| 2 | Consolidation status | `GET /api/consolidation/status` | 3 tiers present |
| 3 | Decay (3x) | `POST /api/decay` three times | normal strength drops, red ink floored at 0.5 |
| 4 | Decay archive | `POST /api/decay/archive` then `GET /api/archive/search` | sub-0.1 entries archived and searchable |
| 5 | Decay status | `GET /api/decay/status` | fading/stable counts |
| 6 | Procedures add | `POST /api/procedures` | created with reinforcement_score 0.5 |
| 7 | Procedures search | `GET /api/procedures/search` | trigram match works |
| 8 | Procedures outcome (success x3) | `POST /api/procedures/{id}/outcome` | reinforcement_score increases |
| 9 | Procedures outcome (fail x5) | `POST /api/procedures/{id}/outcome` | auto-retire triggers |
| 10 | Procedures retire | `POST /api/procedures/{id}/retire` | retired excluded from search |
| 11 | Briefing | `GET /api/briefing?task=build a task API` | LLM-generated structured briefing with red ink + concepts |
| 12 | Anchors | `GET /api/anchors` | All distribution dicts populated |
| 13 | Cost recording | `POST /api/costs` (4 context_types x 3 outcomes) | All recorded |
| 14 | Cost summary | `GET /api/costs/summary` | Aggregates correct |
| 15 | Cost trends | `GET /api/costs/trends` | Trend data returned |
| 16 | Cost list | `GET /api/costs` | Individual records with breakdown |
| 17 | Recall trigram | `GET /api/recall?q=FastAPI&semantic=false` | Results returned, boost advances strength |
| 18 | Recall semantic | `GET /api/recall?q=database&semantic=true` | RRF-ranked results |
| 19 | Auto-classify | `POST /api/memory/classify` | Temporal entries reclassified |
| 20 | Red ink retrieval | `GET /api/memory/red-ink` | Critical entries returned |
| 21 | Smart dedup (matching) | `POST /api/context/smart` with matching conversation | source=smart_dedup, high-similarity dropped |
| 22 | Smart dedup (unrelated) | `POST /api/context/smart` with unrelated conversation | All entries injected |
| 23 | Smart dedup (red ink) | `POST /api/context/smart` with unrelated conversation | Red ink always present |
| 24 | Full context | `GET /api/context` | Markdown with all sections, marker, typed_sections |
| 25 | Touch/boost | `POST /api/memory/touch`, `POST /api/memory/boost` | Strength +0.3 capped at 1.0 |
| 26 | Replace | `POST /api/memory/replace` | Entry replaced |
| 27 | Set priority | `PATCH /api/memory/{index}/priority` | Priority changed |
| 28 | Set type | `PATCH /api/memory/{index}/type` | Type changed |
| 29 | MCP: all 29 tools | Spawn subprocess, initialize, tools/list, call each | All return results |
| 30 | MCP: feature toggle | Restart with `PB_MEMORY=false` | Memory tools hidden |
| 31 | Session recording | Check temporal entries after treatment | New entry with LLM summary |
| 32 | Config hot-reload | `PATCH /api/config` | Change takes effect |
| 33 | Projects list | `GET /api/projects` | poc-benchmark project present |
| 34 | Reindex | `POST /api/reindex` (all tables) | Embeddings regenerated |
| 35 | Dashboard | `GET /dashboard` | HTML returned |
| 36 | Delete memory | `DELETE /api/memory/{id}` | Entry deleted |

## Code Quality Verification

Both arms produce code across 10 turns. Verify treatment code is better:

1. Save all code output from both arms to separate directories
2. Check treatment code for:
   - `os.environ.get()` usage (red ink #1 compliance)
   - Pydantic model validation (red ink #2 compliance)
   - asyncpg connection pooling (concept #3 adherence)
   - Type hints on all functions (concept #4 adherence)
   - Repository pattern in turn 8 (procedural #5 adherence)
   - `httpx.AsyncClient` in tests (procedural #6 adherence)
   - Pagination with limit/offset (temporal #7 reference)
   - `user_id` foreign key (relation #8 reference)
3. Try running the test files both arms produce — do they pass?

## Success Criteria

| Criterion | Threshold | Measurement |
|-----------|-----------|-------------|
| PNEURAL_CTX in treatment llama logs | Must be true | Grep logs for marker |
| PNEURAL_CTX absent from control llama logs | Must be true | Grep logs for marker |
| Marker survives compaction in SQLite DB | Must be true | Query session_message for compaction type |
| Session recorded as temporal entry | Must be true | Query memory for temporal entry after idle |
| Faithfulness improvement | ≥0.3 delta | (treatment_avg - control_avg) / 8 |
| Pairwise win rate | ≥0.65 | treatment_wins / (total - ties - inconclusive) |
| All 36 API exercises pass | Must be true | Each exercise returns expected result |
| Treatment code quality better | Must be true | Checks 2-8 above |
| Red ink always injected in smart dedup | Must be true | Regardless of conversation similarity |
| Red ink never decays below 0.5 | Must be true | After 3 decay cycles |

Verdict: PASS (all true), PARTIAL (most true but some failures), FAIL (core criteria failed)

## Infrastructure Changes on Ryzen

| Change | How |
|--------|-----|
| Fix plugin port | Edit `C:\Users\daivolt\.config\opencode\plugins\pneural-context-plugin\index.mjs` line 1: `8778` → `8779` |
| Enable session recording | Set `PB_RECORD_SESSIONS=true` in `start_opencode_serve.bat` |
| Enable prompt logging | Add `--log-prompt` to llama-server command |
| Set all plugin env vars | `PNEURAL_CONTEXT_URL=http://localhost:8779`, `PB_SMART_DEDUP=true`, `PB_INJECT_ON_START=true`, `PB_INJECT_ON_COMPACT=true` |
| DeepSeek API key | Get free key from platform.deepseek.com, set as `DEEPSEEK_API_KEY` env var |
| Clean state between arms | Use separate opencode sessions, copy SQLite DB between runs |

## Execution Order

1. **Fix infrastructure on ryzen** — plugin port, env vars, llama.cpp `--log-prompt`, restart services
2. **Seed memory** — POST 8 entries via REST API
3. **Run control arm** — plugin disabled, 10-turn conversation, capture logs + DB
4. **Run treatment arm** — plugin enabled, same conversation, capture logs + DB
5. **Run post-conversation API exercises** — all 36 checks
6. **Run evaluation** — faithfulness, pairwise LLM judge, code quality
7. **Generate benchmark report** — structured JSON
8. **Verify success criteria** → PASS/PARTIAL/FAIL
9. **Commit everything** — benchmark script, conversation, seed data, report, code artifacts

## File Structure

```
tests/poc/
├── BENCHMARK_PLAN.md           # This file
├── benchmark.py                # Main orchestrator — runs both arms, evaluation, report
├── conversation.json           # 10-turn fixed conversation script (versioned)
├── seed_data.json              # 8 memory entries to seed (versioned)
├── conversation_runner.py      # Sends prompts to opencode, captures responses + logs
├── log_inspector.py            # Parses llama.cpp logs for PNEURAL_CTX, system prompt
├── db_inspector.py             # Queries opencode SQLite DB (compaction, system messages)
├── llm_judge.py               # DeepSeek Flash pairwise comparison (position-swapped)
├── faithfulness.py            # Checks if responses reference seeded facts
├── api_exercises.py            # Post-conversation API tests (36 exercises)
├── mcp_exercise.py             # MCP subprocess: all 29 tools
├── report_generator.py         # Assembles structured JSON benchmark report
├── code_quality.py             # Analyzes produced code for convention adherence
├── conversation/               # Saved conversation transcripts per arm
│   ├── control/                # Control arm responses + code artifacts
│   └── treatment/              # Treatment arm responses + code artifacts
├── logs/                       # Captured logs
│   ├── control_llama.log       # llama.cpp logs during control arm
│   ├── control_opencode.db     # Copy of opencode SQLite after control
│   ├── treatment_llama.log     # llama.cpp logs during treatment arm
│   └── treatment_opencode.db   # Copy of opencode SQLite after treatment
└── reports/
    └── benchmark_<timestamp>.json  # Final structured report
```

## Benchmark Report Structure

```json
{
  "poc_id": "mem-inject-v1-<timestamp>",
  "git_commit": "<hash>",
  "model": "qwen2.5-coder-7b-instruct-q4_k_m",
  "judge_model": "deepseek-chat",
  "temperature": 0,
  "memory_entries_seeded": 8,
  "conversation_turns": 10,
  "control": {
    "pneural_ctx_in_llama_logs": false,
    "pneural_ctx_in_opencode_db": false,
    "marker_in_compaction": false,
    "session_recorded": false,
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "total_latency_ms": 0,
    "compaction_triggered": false,
    "responses": [],
    "code_artifacts": {}
  },
  "treatment": {
    "pneural_ctx_in_llama_logs": true,
    "pneural_ctx_in_opencode_db": true,
    "marker_in_compaction": true,
    "session_recorded": true,
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "total_latency_ms": 0,
    "compaction_triggered": true,
    "smart_dedup_triggered": true,
    "responses": [],
    "code_artifacts": {}
  },
  "faithfulness": {
    "treatment_avg_references": 0.0,
    "control_avg_references": 0.0,
    "delta": 0.0,
    "per_turn": []
  },
  "pairwise_win_rate": {
    "judge_model": "deepseek-chat",
    "treatment_wins": 0,
    "control_wins": 0,
    "ties": 0,
    "inconclusive": 0,
    "treatment_win_rate": 0.0,
    "per_turn": []
  },
  "code_quality": {
    "treatment_env_var_compliance": true,
    "control_env_var_compliance": false,
    "treatment_pydantic_validation": true,
    "control_pydantic_validation": false,
    "treatment_type_hints": true,
    "control_type_hints": false,
    "treatment_tests_pass": true,
    "control_tests_pass": false
  },
  "api_exercises": {
    "consolidation": {},
    "decay": {},
    "procedures": {},
    "briefing": {},
    "anchors": {},
    "cost_analysis": {},
    "recall": {},
    "smart_dedup": {},
    "full_context": {},
    "mcp_all_tools": {},
    "mcp_feature_toggle": {},
    "session_recording": {},
    "auto_classify": {},
    "config_hot_reload": {},
    "reindex": {},
    "dashboard": {},
    "delete_memory": {}
  },
  "success_criteria": {
    "ctx_in_treatment_logs": {"threshold": true, "actual": true, "pass": true},
    "ctx_absent_in_control_logs": {"threshold": true, "actual": true, "pass": true},
    "marker_survives_compaction": {"threshold": true, "actual": true, "pass": true},
    "session_recorded": {"threshold": true, "actual": true, "pass": true},
    "faithfulness_improvement": {"threshold": 0.3, "actual": 0.0, "pass": false},
    "pairwise_win_rate": {"threshold": 0.65, "actual": 0.0, "pass": false},
    "all_api_exercises_pass": {"threshold": true, "actual": true, "pass": true},
    "code_quality_better": {"threshold": true, "actual": true, "pass": true},
    "red_ink_always_injected": {"threshold": true, "actual": true, "pass": true},
    "red_ink_never_decays_below_0_5": {"threshold": true, "actual": true, "pass": true}
  },
  "verdict": "PASS/PARTIAL/FAIL",
  "timestamp": "2026-07-16T..."
}
```

## Reproducibility

- Conversation script is fixed in `conversation.json` (versioned in git)
- Seed data is fixed in `seed_data.json` (versioned in git)
- Temperature is 0 (deterministic-ish for qwen2.5-coder-7b)
- Git commit hash recorded in report
- Run against opencode **without** plugin → compare with **with** plugin
- `compare_runs()` function can diff two benchmark reports

## Key Insight

The existing 52 PoC tests are unit tests — they verify individual API endpoints in isolation. They never prove that context injection actually reaches the LLM's system prompt. The benchmark proves the full chain:

```
Memory Store → Retrieval/Selection → Context Assembly → Plugin Injection →
System Prompt Construction → LLM Inference → Response Quality
```

If the marker appears in llama.cpp logs AND the treatment responses reference seeded facts AND the marker survives compaction AND the session gets recorded — then and only then is the system proven to work end-to-end.
