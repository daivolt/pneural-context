#!/usr/bin/env python3
"""Add tool-usage procedures to pneural-context procedural memory."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg

from pneural_context.db import pool as pool_mod
from pneural_context.db import procedures as procedures_db

PROCEDURES: list[tuple[str, str, str, list[str]]] = [
    (
        "notebookLM",
        "use browser automation, CDP, session manager, xvfb, login replay, TOTP",
        "browser",
        [
            "Prefer Warden Session Manager at http://10.42.0.1:3100 for authenticated browser sessions.",
            "For headed-required sites (MFA, DLP), ensure xvfb display :99 is running on the dev server.",
            "CDP port map: 9222 for Bloomberg/BBS workflows, 9223 for Applausemail Google profile, 9224 for sheets-sync profile.",
            "Check browser health via /health on the session manager before operations.",
            "For new logins, use session manager login replay + TOTP; never hand-type credentials in scripts.",
            "Capture cookie snapshots after successful login and reuse profiles.",
        ],
    ),
    (
        "notebookLM",
        "read or write Google Sheets, SharePoint Excel, spreadsheet",
        "sheets",
        [
            "Read Google Sheets (single or ad-hoc) -> use sheets-reader MCP, sheets_read tool.",
            "Read/write SharePoint Excel Online -> use sheets-reader MCP, sharepoint_* tools.",
            "Bulk sync DB <-> Google Sheets (BBSheetOS test data) -> use sheets-sync MCP.",
            "BBSheetOS tester workflow -> use bbsheet-sheets MCP.",
            "google-sheets MCP remains disabled; do not re-enable without user confirmation.",
            "Every write via sheets-reader returns a verified value; verify mismatch and retry once.",
        ],
    ),
    (
        "notebookLM",
        "automate Bloomberg Terminal, TA, screenshot, OCR, bloom agent",
        "bloomberg",
        [
            "Use bloom agent at http://10.42.0.89:8765 or test machine http://100.77.108.63:8765.",
            "Use DINO-X vision server at 100.117.7.2:8766 for screen understanding.",
            "Take one screenshot per test step; OCR verify before annotating.",
            "TA (Transcript Analyzer) security field is at fixed layout coordinates per AGENTS rules; verify actual screen.",
            "Reset to starting screen between tests.",
        ],
    ),
]


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


async def main() -> None:
    _load_env(Path(__file__).resolve().parent.parent / ".env")
    database_url = os.environ.get("PNEURAL_DATABASE_URL")
    if not database_url:
        raise RuntimeError("PNEURAL_DATABASE_URL not set")

    pool = await asyncpg.create_pool(database_url)
    if pool is None:
        raise RuntimeError("Failed to create database pool")
    pool_mod.init_pool(pool)
    pool_mod.init_embedding_client(None)

    for project, pattern, task_type, steps in PROCEDURES:
        proc_id = await procedures_db.add_procedure(
            project=project,
            task_pattern=pattern,
            task_type=task_type,
            steps=steps,
            proven_by="tool-procedures-script",
        )
        print(f"Added procedure {proc_id} for {project}: {pattern[:50]}...")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
