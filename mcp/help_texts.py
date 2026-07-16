"""
Help texts for pneural-context MCP server tools.

Each module has a markdown help string and a compact one-line-per-tool version.
The HELPS dict maps module name -> (markdown_help, compact_help).
get_help() returns the appropriate format based on module and format params.
"""

HELP_OVERVIEW = """\
# pneural-context — Persistent Neural Context for LLMs

pneural-context provides memory, recall, consolidation, decay, and cost tracking
for LLM agents. It is designed as a standalone package with a REST API and MCP server.

## Modules

| Module | Description |
|--------|-------------|
| memory | Add, get, replace, search memory entries |
| recall | Semantic search across sessions, chats, and memory |
| red_ink | Critical entries that never decay below 0.5 strength |
| briefing | Task-specific briefing cards aggregating all context |
| procedural | Proven task patterns with reinforcement scoring |
| typed_sections | Auto-classify memory entries into types |
| consolidation | Three-tier memory consolidation pipeline |
| anchors | Environmental anchors for context injection |
| decay | Ebbinghaus forgetting curve with red-ink floor |
| costs | Token cost tracking and efficiency analysis |

Use `pb_help` with a module name for detailed docs. Use format="compact" for one-line-per-tool.
"""

HELP_MEMORY = """\
# Memory Module

Store and retrieve memory entries for projects. Each entry has a text, priority (critical/important/normal),
and type (red/concept/procedural/temporal/relation).

## Tools

### pb_add_memory
Add a new memory entry.
- **project** (required): Project name
- **text** (required): Memory entry text
- **priority**: critical, important, or normal (default: normal)
- **memory_type**: red, concept, procedural, temporal, or relation (optional)
- Note: If priority is "critical", type is automatically set to "red"

### pb_get_memory
Get all memory entries for a project (text only).
- **project** (required): Project name

### pb_get_full_memory
Get all memory entries with full metadata (id, type, priority, strength, timestamps).
- **project** (required): Project name

### pb_replace_memory
Replace a memory entry containing a substring with new text. Uses LIKE match.
- **project** (required): Project name
- **old** (required): Substring to find in existing entry
- **new** (required): Replacement text

### pb_get_context
Get assembled injection context — full markdown with typed sections and red ink for prompt injection.
- **project** (required): Project name
"""

HELP_RECALL = """\
# Recall Module

Search across sessions, chats, and memory.

## Tools

### pb_recall
Search across all stored content with semantic matching.
- **q** (required): Search query
- **project**: Project name (optional)
- **limit**: Max results to return (default: 5)
- **source**: Filter to specific source — "sessions" or "chats" (optional)
- **boost**: Boost matching memory entries via spaced repetition (default: true)
"""

HELP_RED_INK = """\
# Red Ink Module

Red ink entries are critical-priority memories that never decay below 0.5 strength.
They are always injected into context, ensuring critical constraints are never forgotten.

## Tools

### pb_get_red_ink
Get critical (red ink) memory entries.
- **project** (required): Project name
- **min_strength**: Minimum strength threshold (default: 0.0)

### pb_set_priority
Set priority level on a memory entry. Setting to "critical" makes it red ink.
- **project** (required): Project name
- **index** (required): Entry index
- **priority** (required): critical, important, or normal

### pb_touch_entry
Refresh access timestamp on an entry. Prevents decay.
- **project** (required): Project name
- **index** (required): Entry index

### pb_boost_entry
Boost an entry's strength by 0.3 (spaced repetition). Capped at 1.0.
- **project** (required): Project name
- **idx** (required): Entry index
"""

HELP_BRIEFING = """\
# Briefing Module

Generate task-specific briefing cards that aggregate hippocampal recall, topic search,
session search, cultural memory, procedural steps, and lessons.

## Tools

### pb_briefing
Generate a task-specific briefing card.
- **task_description** (required): Description of the task to brief for
- **project** (required): Project name
- **max_tokens**: Max tokens for briefing output (default: 2000)

### pb_get_briefing_anchors
Get environmental anchors: active/completed tasks, recent commits, most-edited files, red-ink reminders.
- **project** (required): Project name
"""

HELP_PROCEDURAL = """\
# Procedural Module

Manage proven task patterns (procedures) with reinforcement scoring.
Procedures capture reusable steps for recurring task patterns and improve via outcome tracking.

## Tools

### pb_list_procedures
List all procedures for a project (non-retired by default).
- **project** (required): Project name

### pb_add_procedure
Manually add a procedure. Usually auto-created on task completion.
- **project** (required): Project name
- **task_pattern** (required): Description of the task pattern
- **steps** (required): List of steps
- **task_type**: Task type classification (optional)

### pb_search_procedures
Search procedures by task description. Uses pg_trgm similarity threshold >= 0.7.
- **project** (required): Project name
- **query** (required): Search query
- **limit**: Max results to return (default: 5)

### pb_procedure_outcome
Record the outcome of applying a procedure. Drives reinforcement score.
- **project** (required): Project name
- **proc_id** (required): Procedure ID
- **outcome** (required): success, fail, or partial

### pb_retire_procedure
Retire a procedure. It will no longer appear in briefings or search.
- **project** (required): Project name
- **proc_id** (required): Procedure ID
"""

HELP_TYPED_SECTIONS = """\
# Typed Sections Module

Auto-classify memory entries into types (red/concept/procedural/temporal/relation)
or manually set entry types.

## Tools

### pb_classify_memory
Auto-classify all unclassified memory entries using LLM enrichment.
Entries with type "temporal" are reclassified via LLM.
- **project** (required): Project name

### pb_set_type
Manually set the type of a memory entry.
- **project** (required): Project name
- **index** (required): Entry index
- **memory_type** (required): red, concept, procedural, temporal, or relation
"""

HELP_CONSOLIDATION = """\
# Consolidation Module

Three-tier consolidation pipeline: immediate → consolidated → timeless.
Creates immediate tier entries from recent memory, extracts insights via LLM,
promotes high-strength entries to timeless, and archives old temporal entries.

## Tools

### pb_trigger_consolidation
Run the consolidation pipeline now.
- **project** (required): Project name
- Returns: immediate_created, insights_created, consolidated_to_timeless, archived_temporal, tiers, errors

### pb_get_consolidation
Get consolidated memory entries. Optionally filter by tier.
- **project** (required): Project name
- **tier**: Filter by tier — immediate, consolidated, or timeless (optional)

### pb_consolidation_status
Show consolidation status with per-tier counts.
- **project** (required): Project name
"""

HELP_ANCHORS = """\
# Anchors Module

Environmental anchors provide context for briefing generation:
active memory count, red ink reminders, top procedures, priority distribution,
tier distribution, and recent entries.

## Tools

### pb_get_anchors
Get environmental anchors for a project.
- **project** (required): Project name
- Returns: active_memory_count, red_ink_count, procedures_count, memory_types,
  priority_distribution, tier_distribution, recent_entries, red_ink_reminders, top_procedures
"""

HELP_DECAY = """\
# Decay Module

Ebbinghaus forgetting curve implementation. All memory entries decay over time
(strength *= decay_factor, default 0.95). Red-ink entries have a floor of 0.5.
Entries below archive threshold (0.1) are moved to archive.

## Tools

### pb_decay_status
Show decay status for all entries: current strength, half-life, last-access time.
- **project** (required): Project name
- Returns: total, below_threshold, fading, stable, entries with strength details

### pb_search_archive
Search archived (forgotten) entries. Below 0.1 strength. Still searchable.
- **project** (required): Project name
- **q**: Search query (empty for all archived)
- **limit**: Max results (default: 20)
"""

HELP_COSTS = """\
# Costs Module

Track token costs for memory injection, selective injection savings, and decay savings.
Used for analyzing context window efficiency.

## Tools

### pb_cost_analysis
Full cost analysis: tokens injected, saved by selective injection, saved by forgetting, effectiveness.
- **project** (required): Project name
- **days**: Number of days to analyze (default: 30)

### pb_cost_trends
Raw per-record cost trend data for charting over time.
- **project** (required): Project name
- **days**: Number of days of trend data (default: 90)

### pb_record_cost
Record a cost observation. Called after context injection and on task completion.
- **project** (required): Project name
- **session_id** (required): Session identifier
- **tokens_injected** (required): Tokens injected into context
- **tokens_saved_injection** (required): Tokens saved by selective injection
- **tokens_saved_forgetting** (required): Tokens saved by forgetting (decay)
- **context_type** (required): Type of context (e.g. 'full', 'briefing', 'anchors')
- **task_outcome** (required): Task outcome (e.g. 'success', 'partial', 'fail')
- **breakdown**: Optional breakdown dict with token details
"""

HELPS = {
    "": (
        HELP_OVERVIEW,
        "pneural-context: persistent neural context. Modules: memory, recall, red_ink, briefing, procedural, typed_sections, consolidation, anchors, decay, costs",
    ),
    "memory": (
        HELP_MEMORY,
        "memory: pb_add_memory, pb_get_memory, pb_get_full_memory, pb_replace_memory, pb_get_context",
    ),
    "recall": (
        HELP_RECALL,
        "recall: pb_recall — search across sessions, chats, and memory",
    ),
    "red_ink": (
        HELP_RED_INK,
        "red_ink: pb_get_red_ink, pb_set_priority, pb_touch_entry, pb_boost_entry",
    ),
    "briefing": (HELP_BRIEFING, "briefing: pb_briefing, pb_get_briefing_anchors"),
    "procedural": (
        HELP_PROCEDURAL,
        "procedural: pb_list_procedures, pb_add_procedure, pb_search_procedures, pb_procedure_outcome, pb_retire_procedure",
    ),
    "typed_sections": (
        HELP_TYPED_SECTIONS,
        "typed_sections: pb_classify_memory, pb_set_type",
    ),
    "consolidation": (
        HELP_CONSOLIDATION,
        "consolidation: pb_trigger_consolidation, pb_get_consolidation, pb_consolidation_status",
    ),
    "anchors": (HELP_ANCHORS, "anchors: pb_get_anchors"),
    "decay": (HELP_DECAY, "decay: pb_decay_status, pb_search_archive"),
    "costs": (HELP_COSTS, "costs: pb_cost_analysis, pb_cost_trends, pb_record_cost"),
}

MODULE_ORDER = [
    "",
    "memory",
    "recall",
    "red_ink",
    "briefing",
    "procedural",
    "typed_sections",
    "consolidation",
    "anchors",
    "decay",
    "costs",
]


def get_help(module: str = "", fmt: str = "markdown", features: dict | None = None) -> str:
    module = module.lower().strip()
    if module not in HELPS:
        module = ""
    md_help, compact_help = HELPS[module]

    if fmt == "compact":
        if module == "":
            lines = []
            for m in MODULE_ORDER:
                _, comp = HELPS[m]
                lines.append(comp)
            return "\n".join(lines)
        return compact_help

    if module == "":
        text = md_help
        if features:
            text += "\n## Enabled Features\n"
            for feat, enabled in features.items():
                status = "✓" if enabled else "✗"
                text += f"- {status} {feat}\n"
        return text

    return md_help
