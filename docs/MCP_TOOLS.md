# MCP Tools Reference

31 tools across 8 feature groups.

## Memory (8)

| Tool | Description |
|------|-------------|
| `pb_add_memory` | Add a memory entry with optional priority and type |
| `pb_get_memory` | Get all memory entries for a project (text only) |
| `pb_get_full_memory` | Get all memory entries with full metadata |
| `pb_replace_memory` | Replace a memory entry containing a substring |
| `pb_set_priority` | Set priority level (critical/important/normal) |
| `pb_set_type` | Set memory type (red/concept/procedural/temporal/relation) |
| `pb_classify_memory` | Auto-classify entries via LLM |
| `pb_search_memory` | Search by text or embedding similarity |

## Context & Recall (4)

| Tool | Description |
|------|-------------|
| `pb_get_context` | Get assembled injection context markdown |
| `pb_recall` | Search sessions/chats/memory with LLM enrichment |
| `pb_briefing` | Generate task-specific briefing card |
| `pb_get_briefing_anchors` | Get active tasks, recent commits, red-ink |

## Procedural Memory (4)

| Tool | Description |
|------|-------------|
| `pb_list_procedures` | List all procedures |
| `pb_add_procedure` | Manually add a procedure |
| `pb_search_procedures` | Search procedures by task description |
| `pb_procedure_outcome` | Record success/fail/partial outcome |
| `pb_retire_procedure` | Retire a flaky procedure |

## Red Ink & Anchors (4)

| Tool | Description |
|------|-------------|
| `pb_get_red_ink` | Get critical entries above strength threshold |
| `pb_get_anchors` | Get environmental anchors |
| `pb_touch_entry` | Refresh access timestamp (prevents decay) |
| `pb_boost_entry` | Boost strength by 0.3 (spaced repetition) |

## Decay & Archive (2)

| Tool | Description |
|------|-------------|
| `pb_decay_status` | Show strength, half-life, last-access for all entries |
| `pb_search_archive` | Search archived (decayed) entries |

## Consolidation (2)

| Tool | Description |
|------|-------------|
| `pb_trigger_consolidation` | Run consolidation pipeline now |
| `pb_get_consolidation` | Get consolidated entries by tier |
| `pb_consolidation_status` | Show per-tier counts |

## Costs (3)

| Tool | Description |
|------|-------------|
| `pb_cost_analysis` | Full cost analysis (tokens injected/saved/forgotten) |
| `pb_cost_trends` | Raw per-record trend data for charting |
| `pb_record_cost` | Record a cost observation after context injection |

## Status (3)

| Tool | Description |
|------|-------------|
| `pb_disable` | Disable context injection for a project |
| `pb_enable` | Re-enable context injection |
| `pb_status` | Check enabled/disabled state |

## Error Telemetry (2)

| Tool | Description |
|------|-------------|
| `pb_errors_list` | List recent logged errors for a project |
| `pb_errors_clear` | Clear all logged errors for a project |
