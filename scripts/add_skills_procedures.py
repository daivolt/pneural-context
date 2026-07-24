#!/usr/bin/env python3
"""Add procedural memory entries matching the 9 new skills."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg

from pneural_context.db import pool as pool_mod
from pneural_context.db import procedures as procedures_db

PROCEDURES: list[tuple[str, str, str, list[str]]] = [
    (
        "code-root",
        "ssh into server, run sudo command, copy file via scp",
        "infra",
        [
            "Look up the target machine in the Tailscale table (dev server, desktop-ryzen, mini, test-machine).",
            "Use sshpass -p 'PASSWORD' with StrictHostKeyChecking=no and ConnectTimeout=5.",
            'For sudo commands, wrap the password in double quotes: echo "PASSWORD" | sudo -S command.',
            "For file copies, use scp with ProxyJump for multi-hop if needed.",
            "Verify health with hostname/uptime before running destructive commands.",
        ],
    ),
    (
        "code-root",
        "deploy to Cloudflare, update tunnel DNS, wrangler",
        "deploy",
        [
            "Run npx wrangler whoami to confirm authentication.",
            "Run npx wrangler deploy from the project directory.",
            "For DNS routes: cloudflared tunnel route dns <tunnel> <host>.nexusvector.com.br.",
            "Keep cert.pem at ~/.cloudflared/cert.pem and never commit it.",
            "Verify the public URL returns HTTP 200 after deploy.",
        ],
    ),
    (
        "notebookLM",
        "use browser automation, CDP, session manager, xvfb",
        "browser",
        [
            "Prefer Warden Session Manager at http://10.42.0.1:3100 for authenticated browser sessions.",
            "For headed-required sites (MFA, DLP), ensure xvfb display :99 is running on dev server.",
            "CDP port map: 9222 Bloomberg/BBS, 9223 Applausemail Google, 9224 sheets-sync.",
            "Check session manager /health before operations.",
            "Use login replay + TOTP for new logins; never hand-type credentials in scripts.",
            "Capture cookie snapshots after successful login and reuse profiles.",
        ],
    ),
    (
        "notebookLM",
        "read or write Google Sheets, SharePoint Excel, spreadsheet",
        "sheets",
        [
            "Read Google Sheets ad-hoc -> sheets-reader MCP sheets_read.",
            "SharePoint Excel Online -> sheets-reader MCP sharepoint_* tools.",
            "Bulk DB sync -> sheets-sync MCP.",
            "BBSheetOS tester workflow -> bbsheet-sheets MCP.",
            "google-sheets MCP is disabled; do not re-enable without user confirmation.",
            "Verify every sheets-reader write by reading back the formula bar.",
        ],
    ),
    (
        "engineering-standards",
        "run CI gate before deploy, check tests lint types",
        "quality",
        [
            "Run pytest tests/ -v -m 'not integration'.",
            "Run ruff check . and ruff format --check .",
            "Run mypy . for Python projects or npm run typecheck for TypeScript.",
            "Gate must pass twice in a row before proceeding.",
            "If the gate fails, fix and rerun before any deploy.",
        ],
    ),
    (
        "engineering-standards",
        "set up new Python project, lint, type check, tests",
        "setup",
        [
            "Create pyproject.toml with hatchling, ruff, mypy, pytest config.",
            "Create src/<module>/ and tests/ directories.",
            "Add .env.example and README.md.",
            "Create AGENTS.md as a thin pointer to pneural-context project.",
            "Install dev deps with pip install -e '.[dev]' and run the CI gate.",
        ],
    ),
    (
        "engineering-standards",
        "create new MCP server, tools, handlers",
        "mcp",
        [
            "Choose TypeScript (fastmcp) or Python (mcp.server.fastmcp).",
            "Define tools with zod schemas (TS) or typed signatures (Python).",
            "Use stdio transport for opencode local MCPs.",
            "Add build/start scripts and tsconfig/pyproject.",
            "Register in opencode.json mcp section and test manually before enabling.",
        ],
    ),
    (
        "engineering-standards",
        "scan codebase for secrets, credentials, keys",
        "security",
        [
            "Grep for apiKey/api_key/client_secret/password/token followed by a long quoted value.",
            "Inspect credentials.json, service_account.json, *.pem, *.key, *.ppk, .env files.",
            "Check AGENTS.full.md backups for plaintext secrets.",
            "Run gitleaks detect --source . --verbose if available.",
            "Rotate exposed secrets, move to .env or vault, update .gitignore.",
        ],
    ),
    (
        "BBSheetOS",
        "push BBSheetOS bundle to Google Apps Script, build, promote",
        "deploy",
        [
            "Run ./build-bundle.sh in BBSheetOS/.",
            "Run ./push-test.sh and verify in the test sheet.",
            "Run ./push-beta.sh for wider validation.",
            "Only run ./promote.sh after test/beta verification.",
            "Confirm the pushed version appears in the GAS dashboard.",
        ],
    ),
]


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
            proven_by="skills-procedures-script",
        )
        print(f"Added procedure {proc_id} for {project}: {pattern[:50]}...")

    await pool.close()


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


if __name__ == "__main__":
    asyncio.run(main())
