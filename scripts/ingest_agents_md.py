#!/usr/bin/env python3
"""Ingest AGENTS.md and .standards files into pneural-context as typed memory."""

from __future__ import annotations

import argparse
import asyncio
import os
import re
from pathlib import Path

import asyncpg

from pneural_context.db import memory as memory_db
from pneural_context.db import pool as pool_mod

PROJECT_ROOT = Path("/mnt/external-drive/code")
GLOBAL_CONFIG = Path.home() / ".config" / "opencode"

FILES: list[tuple[Path, str]] = [
    (PROJECT_ROOT / "AGENTS.md", "code-root"),
    (GLOBAL_CONFIG / "AGENTS.md", "opencode-global"),
    (PROJECT_ROOT / "notebookLM" / "AGENTS.md", "notebookLM"),
    (PROJECT_ROOT / "warden" / "AGENTS.md", "warden"),
    (PROJECT_ROOT / "BBSheetOS" / "AGENTS.md", "BBSheetOS"),
    (PROJECT_ROOT / "timeTracking" / "AGENTS.md", "timeTracking"),
    (PROJECT_ROOT / "wardensec" / "AGENTS.md", "wardensec"),
    (PROJECT_ROOT / "awserver" / "AGENTS.md", "awserver"),
    (PROJECT_ROOT / "memoria" / "AGENTS.md", "memoria"),
    (PROJECT_ROOT / "memoria-agents" / "AGENTS.md", "memoria-agents"),
    (PROJECT_ROOT / "crush" / "AGENTS.md", "crush"),
    (PROJECT_ROOT / "cloudvault" / "AGENTS.md", "cloudvault"),
    (PROJECT_ROOT / "loadbalancer" / "AGENTS.md", "loadbalancer"),
    (PROJECT_ROOT / "bloomberg-visual-sota" / "AGENTS.md", "bloomberg-visual-sota"),
    (PROJECT_ROOT / "mercadolibre" / "AGENTS.md", "mercadolibre"),
    (PROJECT_ROOT / "opencode" / "AGENTS.md", "opencode"),
    (PROJECT_ROOT / "alternatives" / "AGENTS.md", "alternatives"),
    (PROJECT_ROOT / "nexus-cli" / "AGENTS.md", "nexus-cli"),
]

STANDARDS_DIR = GLOBAL_CONFIG / ".standards"


RED_INK_KEYWORDS = {
    "critical",
    "never",
    "warning",
    "forbidden",
    "do not",
    "must not",
    "always",
    "non-negotiable",
}

PROCEDURE_KEYWORDS = {
    "deploy",
    "build",
    "push",
    "run ",
    "how to",
    "procedure",
    "workflow",
    "steps",
    "guide",
}

RELATION_KEYWORDS = {
    "port",
    "service",
    "machine",
    "database",
    "table",
    "host",
    "ip",
    "url",
}


def classify(header: str, body: str) -> tuple[str, str]:
    """Return (priority, memory_type)."""
    text = f"{header} {body}".lower()
    if any(kw in text for kw in RED_INK_KEYWORDS):
        return "critical", "red"
    if any(kw in text for kw in PROCEDURE_KEYWORDS):
        return "important", "procedural"
    if any(kw in text for kw in RELATION_KEYWORDS):
        return "normal", "relation"
    return "normal", "concept"


def parse_sections(path: Path, project: str) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    # Split by markdown headers (## or ###)
    parts = re.split(r"\n(?=##+\s)", text)
    sections: list[dict] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines = part.splitlines()
        header_match = re.match(r"^(##+)\s+(.*)", lines[0])
        if not header_match:
            continue
        header = header_match.group(2).strip()
        body = "\n".join(lines[1:]).strip()
        if not body or len(body) < 20:
            continue
        priority, memory_type = classify(header, body)
        sections.append(
            {
                "project": project,
                "header": header,
                "body": body,
                "priority": priority,
                "memory_type": memory_type,
            }
        )
    return sections


def parse_standards(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    parts = re.split(r"\n(?=##+\s)", text)
    sections: list[dict] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines = part.splitlines()
        header_match = re.match(r"^(##+)\s+(.*)", lines[0])
        if not header_match:
            continue
        header = header_match.group(2).strip()
        body = "\n".join(lines[1:]).strip()
        if not body or len(body) < 20:
            continue
        priority, memory_type = classify(header, body)
        sections.append(
            {
                "project": "engineering-standards",
                "header": header,
                "body": body,
                "priority": priority,
                "memory_type": memory_type,
            }
        )
    return sections


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key not in os.environ:
            os.environ[key] = value


async def ingest(dry_run: bool = False) -> None:
    _load_env(Path(__file__).resolve().parent.parent / ".env")
    database_url = os.environ.get("PNEURAL_DATABASE_URL")
    if not database_url:
        raise RuntimeError("PNEURAL_DATABASE_URL not set")

    pool = await asyncpg.create_pool(database_url)
    if pool is None:
        raise RuntimeError("Failed to create database pool")
    pool_mod.init_pool(pool)
    pool_mod.init_embedding_client(None)

    sections: list[dict] = []
    for path, project in FILES:
        if path.exists():
            sections.extend(parse_sections(path, project))

    if STANDARDS_DIR.exists():
        for path in STANDARDS_DIR.glob("*.md"):
            sections.extend(parse_standards(path))

    print(f"Parsed {len(sections)} sections")

    if dry_run:
        for s in sections:
            print(f"[{s['project']}] {s['priority']}/{s['memory_type']} {s['header'][:60]}")
        return

    inserted = 0
    skipped = 0
    for s in sections:
        text = f"{s['header']}\n\n{s['body']}"
        entry_id = await memory_db.add_memory_entry(
            project=s["project"],
            text=text,
            priority=s["priority"],
            memory_type=s["memory_type"],
            source_system="agents-md-ingest",
        )
        if entry_id > 0:
            inserted += 1
        else:
            skipped += 1

    print(f"Inserted {inserted}, skipped/duplicate {skipped}")
    await pool.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest AGENTS.md into pneural-context")
    parser.add_argument("--dry-run", action="store_true", help="Print without inserting")
    args = parser.parse_args()
    asyncio.run(ingest(dry_run=args.dry_run))
