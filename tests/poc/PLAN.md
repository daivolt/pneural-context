# PoC Test Suite — Final Plan

## Overview

A pytest test suite that runs **real opencode sessions** on desktop-ryzen against the pneural-context dev server (port 8779) with real LLM (qwen2.5-coder-7b on llama.cpp :8080) and real embeddings (nomic-embed-text on Ollama :11434). Every test produces structured metrics collected into a JSON telemetry file for post-run analysis and cross-cycle comparison. **No simulated tests.**

## Machines

| Machine | Tailscale IP | LAN IP | Role |
|---------|-------------|--------|------|
| mini (dev) | 100.121.245.69 | — | Where we write code |
| mediserv | 100.126.64.13 | 10.42.0.213 | Production pneural-context (:8778) |
| desktop-ryzen | 100.117.7.2 | 10.42.0.89 | Dev/test pneural-context (:8779) + opencode |

**Ryzen SSH**: `sshpass -p 'icaro9$d' ssh daivolt@10.42.0.89` (PowerShell commands)
**Ryzen credentials**: `daivolt@gmail.com` / `icaro9$d`
**Ryzen is Windows** — all commands via PowerShell

## Services on Ryzen

| Service | Port | Details |
|---------|------|---------|
| pneural-context | 8779 | Windows Scheduled Task `PneuralContext`, venv at `C:\pneural-context\.venv\` |
| llama.cpp | 8080 | qwen2.5-coder-7b-instruct-q4_k_m.gguf |
| Ollama | 11434 | nomic-embed-text |
| opencode serve | 4096 | Started by test suite, config at `C:\Users\daivolt\.config\opencode\` |
| PostgreSQL 16 | 5432 | DB `pneural_test`, user `pneural`, pass `pneural_test_2026` |

## Directory Structure

```
tests/poc/
├── PLAN.md                        # This file
├── conftest.py                    # Fixtures + telemetry collector
├── telemetry.py                   # Metrics collection, JSON export, compare_runs()
├── test_01_infra.py              # All services up + opencode configured
├── test_02_context_injection.py  # Real session → context injected into system prompt
├── test_03_smart_dedup.py        # Multi-message session → dedup zones verified
├── test_04_session_recording.py  # Real session → idle → summary stored in DB
├── test_05_compaction.py        # Long session → compaction → marker survives
├── test_06_mcp_tools.py          # MCP stdio subprocess → real tool calls
├── test_07_lifecycle.py          # Multi-session lifecycle: add→inject→consolidate→decay
├── test_08_plugin_hooks.py      # Node subprocess → plugin .mjs with real HTTP
├── test_09_cost_analysis.py     # Cost recording → analysis → trends → effectiveness
├── run_poc.py                    # Orchestrator: setup→run→collect→export report
└── reports/                      # Generated telemetry JSONs (gitignored)
    └── poc_YYYYMMDD_HHMMSS.json  # Timestamped run reports
```

## Telemetry & Data Analysis Layer

Every test records metrics into a shared telemetry object. After the full run, a JSON report is exported to `reports/poc_<timestamp>.json`:

```json
{
  "run_id": "poc_20260716_182000",
  "timestamp": "2026-07-16T18:20:00Z",
  "environment": {
    "pneural_url": "http://localhost:8779",
    "llm_model": "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
    "embed_model": "nomic-embed-text",
    "opencode_version": "1.14.24",
    "project": "poc-test"
  },
  "tests": {
    "test_02_context_injection": {
      "duration_seconds": 12.3,
      "memory_entries_seeded": 5,
      "context_entries_returned": 4,
      "marker_in_system_prompt": true,
      "last_accessed_updated": true,
      "assistant_referenced_memory": true,
      "tokens_injected": 847,
      "pass": true
    }
  },
  "summary": {
    "total_tests": 9,
    "passed": 8,
    "failed": 1,
    "total_duration_seconds": 145.2,
    "total_tokens_injected": 3421,
    "total_tokens_saved": 892
  }
}
```

`telemetry.py` also provides `compare_runs(report_a, report_b)` to diff two runs — so in next cycles you can see exactly which metrics changed.

## opencode.json Configuration (to create on ryzen)

Path: `C:\Users\daivolt\.config\opencode\opencode.json`

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "llamacpp/qwen2.5-coder-7b",
  "provider": {
    "llamacpp": {
      "name": "llama.cpp",
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "http://localhost:8080/v1"
      },
      "models": {
        "qwen2.5-coder-7b": {
          "name": "qwen2.5-coder-7b-instruct"
        }
      }
    }
  },
  "plugin": [
    "C:\\Users\\daivolt\\.config\\opencode\\plugins\\pneural-context-plugin"
  ]
}
```

## Plugin Setup on Ryzen

1. Create directory: `C:\Users\daivolt\.config\opencode\plugins\pneural-context-plugin\`
2. Copy `plugins/opencode/pneural-context.mjs` → `index.mjs` in that directory
3. Create `package.json` with `{"name": "pneural-context-plugin", "main": "index.mjs"}`
4. Set env vars for opencode process:
   - `PNEURAL_CONTEXT_URL=http://localhost:8779`
   - `PB_RECORD_SESSIONS=true`
   - `PB_SMART_DEDUP=true`
   - `PB_INJECT_ON_START=true`
   - `PB_INJECT_ON_COMPACT=true`

## Project Config

Update `C:\pneural-context\.pneural-context.json`:
```json
{"project": "poc-test"}
```

## opencode serve Interaction Pattern

```python
# Create session
resp = httpx.post("http://localhost:4096/session")
session_id = resp.json()["id"]

# Send message
resp = httpx.post(f"http://localhost:4096/session/{session_id}/message", json={
    "role": "user",
    "parts": [{"type": "text", "text": "What context do you have?"}]
})
assistant_msg = resp.json()

# SSE event stream
async with httpx.stream("GET", "http://localhost:4096/event") as stream:
    # Read events for session.idle, session.created, etc.
```

## Test Phases

### test_01_infra.py — Infrastructure Verification

- GET http://localhost:8779/health → status ok, version matches
- GET http://localhost:8779/api/config → database_url_set=true, embed_backend=ollama
- GET http://localhost:8080/v1/models → qwen2.5-coder-7b model present
- GET http://localhost:11434/api/tags → nomic-embed-text present
- `opencode --version` → 1.14.24
- opencode.json exists with plugin registered
- opencode serve on :4096 responds
- **Telemetry**: service versions, response times, model names

### test_02_context_injection.py — Context Injection via Real Session

1. Seed 5 memory entries via REST API (mix of normal/important/critical, different types)
2. Record `last_accessed` timestamps before session
3. POST http://localhost:4096/session → create session
4. POST http://localhost:4096/session/{id}/message → send "What context do you have about this project?"
5. Capture assistant response JSON
6. GET /api/memory?project=poc-test → check `last_accessed` timestamps advanced (proves context fetch)
7. Verify assistant response references at least one seeded memory entry
8. **Telemetry**: entries_seeded, entries_returned, marker_present, last_accessed_updated, assistant_referenced_memory, tokens, response_time

### test_03_smart_dedup.py — Smart Dedup Zones

1. Seed entries: 3 highly similar (about "API testing"), 3 dissimilar (about "database", "firewall", "deployment"), 1 red-ink critical
2. POST /api/context/smart with conversation text matching "API testing" → verify source=smart_dedup, high-similarity entries deduplicated
3. POST /api/context/smart with conversation text matching nothing → verify all injected (low similarity zone)
4. POST /api/context/smart with conversation text partially matching → verify mid-zone behavior
5. Run real opencode session sending 3 messages about "API testing" → verify dedup triggered
6. **Telemetry**: dedup_source, high_dropped_count, low_injected_count, red_ink_always_injected, threshold_high, threshold_low

### test_04_session_recording.py — Session Recording

1. Verify PB_RECORD_SESSIONS=true in opencode env
2. Run real opencode session with 3 message exchanges (ask about a coding task)
3. End session / wait for session.idle event (via SSE or poll)
4. GET /api/memory?project=poc-test → verify new entry with session summary
5. Verify summary is LLM-generated (longer/different from raw title)
6. GET /api/memory/full?project=poc-test → verify memory_type=temporal
7. **Telemetry**: messages_in_session, summary_length, summary_is_llm_generated, entry_id, recording_time_seconds

### test_05_compaction.py — Compaction Marker Survival

1. Seed several memory entries including red-ink
2. Run long opencode session: 10+ messages to fill context window and trigger compaction
3. After compaction, verify session's compacted summary still contains PNEURAL_CTX marker
4. Verify preservation instruction was injected (plugin output.context)
5. Verify red-ink entries survive compaction (not summarized away)
6. **Telemetry**: messages_before_compaction, compaction_triggered, marker_survived, red_ink_survived, context_length_before, context_length_after

### test_06_mcp_tools.py — MCP Server via stdio

1. Spawn `python -m pneural_context.mcp_server.server` with `PNEURAL_URL=http://localhost:8779` as subprocess
2. Send MCP initialize → tools/list → verify all 32 tools present
3. Call each tool category with real data and verify HTTP side effects:
   - pb_add_memory → verify via REST GET /api/memory
   - pb_get_memory → returns seeded data
   - pb_recall → search works (trigram fallback)
   - pb_get_red_ink → critical entries returned
   - pb_set_priority → verify priority changed
   - pb_trigger_consolidation → verify consolidated entries created
   - pb_briefing → verify LLM-generated briefing returned
   - pb_record_cost → verify cost recorded
   - pb_add_procedure → verify via GET /api/procedures
   - pb_boost_entry → verify strength increased
   - pb_classify_memory → verify types assigned
   - pb_decay_status → verify status returned
4. Test feature toggle: restart subprocess with PB_MEMORY=false → verify memory tools hidden
5. **Telemetry**: tools_listed, tools_called, tools_passed, tools_failed, feature_toggle_works

### test_07_lifecycle.py — Multi-Session Lifecycle

1. **Session 1**: Start opencode session, add memory via MCP ("The deployment server is at 10.42.0.89"), end session
2. **Session 2**: Start new session, send "What do you know about the deployment server?" → verify injected context includes entry from Session 1 → add another memory ("PostgreSQL runs on port 5432") → trigger consolidation → end session
3. **Session 3**: Start new session → verify consolidated entries in context → trigger decay → verify red-ink preserved, temporal decayed → verify decay status → end session
4. GET /api/costs/summary?project=poc-test → verify cost records across all 3 sessions
5. **Telemetry**: sessions_run, memory_added_per_session, context_entries_per_session, consolidated_count, decayed_count, red_ink_preserved, total_cost

### test_08_plugin_hooks.py — Plugin Direct Invocation

1. Node subprocess loads pneural-context.mjs with real fetch → pneural-context:8779
2. Create minimal ctx mock with real opencode session messages
3. Test `experimental.chat.system.transform`: call hook → verify output.system contains PNEURAL_CTX markdown
4. Test cache: call hook twice within 5s → verify cached (same marker) → wait TTL → verify fresh fetch (new marker)
5. Test `experimental.session.compacting`: call hook → verify output.context contains preservation instruction with marker
6. Test event `session.created`: call hook → verify pre-warm fetch (last_accessed updated)
7. Test event `session.idle` with PB_RECORD_SESSIONS=true: call hook → verify POST /api/session/record called
8. Test project resolution: PNEURAL_PROJECT env → .pneural-context.json → basename fallback
9. **Telemetry**: hooks_tested, cache_ttl_verified, project_resolution_chain, all_hooks_passed

### test_09_cost_analysis.py — Cost Tracking & Analysis

1. Record costs across multiple simulated sessions with varying context types (full, briefing, anchors, smart_dedup)
2. GET /api/costs/summary?project=poc-test → verify aggregate stats (total injected, total saved, effectiveness ratio)
3. GET /api/costs/trends?project=poc-test → verify trend data returned
4. GET /api/costs?project=poc-test → verify individual records
5. Verify breakdown field stored correctly when provided
6. **Telemetry**: costs_recorded, total_injected, total_saved, effectiveness_ratio, by_context_type

## Post-Run: No Cleanup, Inspection-Ready

After test run:

- All opencode sessions remain in `C:\Users\daivolt\.local\share\opencode\opencode.db`
- All pneural-context entries remain in PostgreSQL `pneural_test` DB for project `poc-test`
- Telemetry report at `reports/poc_<timestamp>.json`
- Use `run_poc.py --clean` later to purge test data

## Cross-Cycle Comparison

```bash
# Run PoC, get report
python tests/poc/run_poc.py

# Compare two runs
python tests/poc/run_poc.py --compare reports/poc_20260716_182000.json reports/poc_20260717_100000.json

# Output: diff of all metrics, highlighting regressions/improvements
```

## What This Catches That Current Tests Miss

| Gap | PoC Test |
|-----|----------|
| Plugin never loaded/tested | test_08 |
| MCP server never spawned via stdio | test_06 |
| Context injection into real system prompt | test_02 |
| Smart dedup with real conversation | test_03 |
| Session recording on idle | test_04 |
| Compaction marker survival | test_05 |
| Multi-session lifecycle | test_07 |
| Cost analysis effectiveness | test_09 |
| Feature toggle behavior | test_06 |
| Project resolution chain | test_08 |
| Cache TTL behavior | test_08 |
| Touch-on-inject side effect | test_02 |

## Known Bugs (to verify in PoC)

1. `pb_recall` with `boost=true` fails — boolean not serialized to string in MCP server (yarl query param encoding)
2. `pb_procedure_outcome` maps "partial" outcome to `success=false`, collapsing partial and fail
3. `PB_SMART_DEDUP` defaults true in code but false in README
4. MCP `pb_recall` has no `semantic` param — vector search unreachable via MCP
5. No MCP tool for `DELETE /api/memory/{id}`, `POST /api/reindex`, or config endpoints

## Setup Steps (performed by run_poc.py orchestrator)

1. Create `C:\Users\daivolt\.config\opencode\opencode.json` (see config above)
2. Create plugin directory `C:\Users\daivolt\.config\opencode\plugins\pneural-context-plugin\` with `index.mjs` + `package.json`
3. Update `C:\pneural-context\.pneural-context.json` → `{"project": "poc-test"}`
4. Start opencode serve on port 4096
5. Clean pneural-context DB for project `poc-test` (delete all entries, costs, consolidated, procedures)
6. Run pytest with telemetry collection
7. Export telemetry report to `reports/poc_<timestamp>.json`
