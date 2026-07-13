from __future__ import annotations

import logging
import time
from typing import Any

from . import pb_db
from .pb_llm import LLMClient

logger = logging.getLogger("pneural_context.pb_engine")


def _to_epoch(val: Any) -> float:
    from datetime import datetime

    if isinstance(val, datetime):
        return val.timestamp()
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


async def auto_classify(
    project: str, llm: LLMClient | None = None, pool=None
) -> dict[str, Any]:
    entries = await pb_db.get_memory_entries_full(project, pool=pool)
    unclassified = [e for e in entries if e.get("memory_type") == "temporal"]
    if not unclassified:
        return {"project": project, "classified": 0, "total": len(entries)}
    if llm is None:
        return {
            "project": project,
            "classified": 0,
            "total": len(entries),
            "error": "no LLM client",
        }
    classified = 0
    for entry in unclassified:
        try:
            mtype = await llm.classify(entry["entry"])
            ok = await pb_db.update_memory_type(project, entry["id"], mtype, pool=pool)
            if ok:
                classified += 1
        except Exception:
            logger.warning(f"Classification failed for entry {entry['id']}")
    return {"project": project, "classified": classified, "total": len(entries)}


async def run_consolidation(
    project: str, llm: LLMClient | None = None, pool=None
) -> dict[str, Any]:
    entries = await pb_db.get_memory_entries_full(project, pool=pool)
    if not entries:
        return {"project": project, "consolidated": 0, "reason": "no entries"}

    result: dict[str, Any] = {
        "immediate_created": 0,
        "insights_created": 0,
        "consolidated_to_timeless": 0,
        "archived_temporal": 0,
        "errors": 0,
    }

    critical = [e for e in entries if e.get("priority") == "critical"]
    important = [e for e in entries if e.get("priority") == "important"]
    normal = [e for e in entries if e.get("priority") == "normal"]

    existing_immediate = await pb_db.get_consolidated_by_tier(
        project, "immediate", pool=pool
    )
    if not existing_immediate:
        if critical:
            content = " | ".join(e["entry"][:200] for e in critical[:10])
        elif important:
            content = " | ".join(e["entry"][:200] for e in important[:10])
        else:
            content = " | ".join(e["entry"][:200] for e in entries[:10])
        await pb_db.add_consolidated(project, "immediate", content, pool=pool)
        result["immediate_created"] = 1

    groups_to_consolidate = []
    if len(important) >= 3:
        groups_to_consolidate.append(("consolidated", important[:20]))
    if len(normal) >= 3:
        groups_to_consolidate.append(("consolidated", normal[:20]))
    if len(critical) >= 3:
        groups_to_consolidate.append(("consolidated", critical[:20]))

    total_insights = 0
    for tier, group in groups_to_consolidate:
        if llm is None:
            content = " | ".join(e["entry"][:200] for e in group)
            await pb_db.add_consolidated(project, tier, content, pool=pool)
            total_insights += 1
            continue
        try:
            llm_result = await llm.consolidate(group)
            insights = llm_result.get("insights", [])
            mtype = llm_result.get("type", "concept")
            priority = llm_result.get("priority", "normal")
            for insight in insights:
                content = insight.strip()
                if not content:
                    continue
                if mtype not in ("concept", "procedural", "relation", "temporal"):
                    mtype = "concept"
                await pb_db.add_consolidated(
                    project,
                    tier,
                    content,
                    memory_type=mtype,
                    priority=priority,
                    pool=pool,
                )
                total_insights += 1
        except Exception:
            logger.warning(f"LLM consolidation failed for {project}")
            content = " | ".join(e["entry"][:200] for e in group)
            await pb_db.add_consolidated(project, tier, content, pool=pool)
            total_insights += 1
            result["errors"] += 1

    result["insights_created"] = total_insights

    consolidated_entries = await pb_db.get_consolidated_for_injection(
        project, pool=pool
    )
    for entry in consolidated_entries:
        if entry.get("priority") == "critical":
            ok = await pb_db.promote_consolidated(entry["id"], "timeless", pool=pool)
            if ok:
                result["consolidated_to_timeless"] += 1

    for entry in consolidated_entries:
        strength = entry.get("strength", 0.5)
        source_count = len(entry.get("source_sessions", []) or [])
        if (strength >= 0.8 or source_count >= 3) and entry.get(
            "priority"
        ) != "critical":
            ok = await pb_db.promote_consolidated(entry["id"], "timeless", pool=pool)
            if ok:
                result["consolidated_to_timeless"] += 1

    now = time.time()
    thirty_days_ago = now - 30 * 86400
    old_temporal = [
        e
        for e in entries
        if e.get("memory_type") == "temporal"
        and e.get("priority") == "normal"
        and _to_epoch(e.get("created_at", 0)) < thirty_days_ago
    ]
    for entry in old_temporal[:50]:
        ok = await pb_db.archive_memory_entry(entry["id"], pool=pool)
        if ok:
            result["archived_temporal"] += 1

    tier_counts: dict[str, int] = {}
    for tier in ("immediate", "consolidated", "timeless"):
        tier_entries = await pb_db.get_consolidated_by_tier(project, tier, pool=pool)
        tier_counts[tier] = len(tier_entries)
    result["tiers"] = dict(tier_counts)

    return result


async def generate_briefing(
    project: str,
    task_description: str = "",
    llm: LLMClient | None = None,
    pool=None,
) -> dict[str, Any]:
    entries = await pb_db.get_memory_entries_full(project, pool=pool)
    red_ink = [e for e in entries if e.get("priority") == "critical"]
    consolidated = await pb_db.get_consolidated_for_injection(project, pool=pool)
    procedures = await pb_db.list_procedures(project, retired=False, pool=pool)
    top_procedures = sorted(
        procedures, key=lambda p: p.get("reinforcement_score", 0), reverse=True
    )[:5]

    lines = [f"# Briefing: {project}", ""]

    if red_ink:
        lines.append("## RED INK (CRITICAL)")
        for e in red_ink[:5]:
            lines.append(f"- {e['entry']}")
        lines.append("")

    important = [e for e in entries if e.get("priority") == "important"]
    if important:
        lines.append("## Important")
        for e in important[:5]:
            lines.append(f"- [{e.get('memory_type', 'temporal')}] {e['entry'][:120]}")
        lines.append("")

    if top_procedures:
        lines.append("## Key Procedures")
        for p in top_procedures:
            steps = p.get("steps", [])
            steps_str = ", ".join(str(s)[:40] for s in steps[:3]) if steps else ""
            lines.append(f"- {p['task_pattern']}: {steps_str}")
        lines.append("")

    if consolidated:
        lines.append("## Consolidated Knowledge")
        for c in consolidated[:5]:
            lines.append(f"- [{c.get('tier', '?')}] {c['content'][:200]}")
        lines.append("")

    recent = sorted(entries, key=lambda e: e.get("last_accessed", 0), reverse=True)[:5]
    if recent:
        lines.append("## Recent Memory")
        for e in recent:
            lines.append(f"- [{e.get('memory_type', 'temporal')}] {e['entry'][:120]}")
        lines.append("")

    if task_description:
        lines.append("## Task Context")
        lines.append(f"- {task_description}")
        lines.append("")

    context_text = "\n".join(lines)

    if llm and task_description:
        try:
            briefing = await llm.generate_briefing(
                context_text + f"\n\nTask: {task_description}"
            )
            return {
                "project": project,
                "task": task_description,
                "briefing": briefing,
                "context_entries": len(entries),
                "red_ink_count": len(red_ink),
                "procedures_count": len(top_procedures),
                "consolidated_count": len(consolidated),
            }
        except Exception:
            pass

    return {
        "project": project,
        "task": task_description,
        "briefing": context_text,
        "context_entries": len(entries),
        "red_ink_count": len(red_ink),
        "procedures_count": len(top_procedures),
        "consolidated_count": len(consolidated),
    }


async def generate_anchors(project: str, pool=None) -> dict[str, Any]:
    entries = await pb_db.get_memory_entries_full(project, pool=pool)
    red_ink = [e for e in entries if e.get("priority") == "critical"]
    procedures = await pb_db.list_procedures(project, retired=False, pool=pool)
    consolidated = await pb_db.get_consolidated_for_injection(project, pool=pool)

    recent = sorted(entries, key=lambda e: e.get("last_accessed", 0), reverse=True)[:5]
    active_types: dict[str, int] = {}
    for e in entries:
        t = e.get("memory_type", "temporal")
        active_types[t] = active_types.get(t, 0) + 1

    priority_counts: dict[str, int] = {}
    for e in entries:
        p = e.get("priority", "normal")
        priority_counts[p] = priority_counts.get(p, 0) + 1

    tier_counts: dict[str, int] = {}
    for c in consolidated:
        t = c.get("tier", "consolidated")
        tier_counts[t] = tier_counts.get(t, 0) + 1

    anchors: dict[str, Any] = {
        "project": project,
        "active_memory_count": len(entries),
        "red_ink_count": len(red_ink),
        "procedures_count": len(procedures),
        "consolidated_count": len(consolidated),
        "memory_types": active_types,
        "priority_distribution": priority_counts,
        "tier_distribution": tier_counts,
        "recent_entries": [
            {
                "id": e["id"],
                "entry": e["entry"][:120],
                "type": e.get("memory_type", "temporal"),
                "priority": e.get("priority", "normal"),
            }
            for e in recent
        ],
        "red_ink_reminders": [
            {"id": e["id"], "entry": e["entry"][:120]} for e in red_ink[:5]
        ],
        "top_procedures": [
            {
                "id": p.get("id"),
                "pattern": p["task_pattern"],
                "score": p.get("reinforcement_score", 0),
                "steps": p.get("steps", [])[:3],
            }
            for p in sorted(
                procedures, key=lambda p: p.get("reinforcement_score", 0), reverse=True
            )[:5]
        ],
        "_ts": time.time(),
    }
    return anchors
