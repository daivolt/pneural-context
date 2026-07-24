#!/usr/bin/env python3
"""Back up AGENTS.md files and replace them with thin KB pointers."""

from __future__ import annotations

import argparse
from pathlib import Path

FILES: list[tuple[Path, str]] = [
    (Path("/mnt/external-drive/code/AGENTS.md"), "code-root"),
    (Path.home() / ".config" / "opencode" / "AGENTS.md", "opencode-global"),
    (Path("/mnt/external-drive/code/notebookLM/AGENTS.md"), "notebookLM"),
    (Path("/mnt/external-drive/code/warden/AGENTS.md"), "warden"),
    (Path("/mnt/external-drive/code/BBSheetOS/AGENTS.md"), "BBSheetOS"),
    (Path("/mnt/external-drive/code/timeTracking/AGENTS.md"), "timeTracking"),
    (Path("/mnt/external-drive/code/wardensec/AGENTS.md"), "wardensec"),
    (Path("/mnt/external-drive/code/awserver/AGENTS.md"), "awserver"),
    (Path("/mnt/external-drive/code/memoria/AGENTS.md"), "memoria"),
    (Path("/mnt/external-drive/code/memoria-agents/AGENTS.md"), "memoria-agents"),
    (Path("/mnt/external-drive/code/crush/AGENTS.md"), "crush"),
    (Path("/mnt/external-drive/code/cloudvault/AGENTS.md"), "cloudvault"),
    (Path("/mnt/external-drive/code/loadbalancer/AGENTS.md"), "loadbalancer"),
    (Path("/mnt/external-drive/code/bloomberg-visual-sota/AGENTS.md"), "bloomberg-visual-sota"),
    (Path("/mnt/external-drive/code/mercadolibre/AGENTS.md"), "mercadolibre"),
    (Path("/mnt/external-drive/code/opencode/AGENTS.md"), "opencode"),
    (Path("/mnt/external-drive/code/alternatives/AGENTS.md"), "alternatives"),
    (Path("/mnt/external-drive/code/nexus-cli/AGENTS.md"), "nexus-cli"),
]


def pointer_template(title: str, project: str, run_cmd: str, red_ink: list[str]) -> str:
    red_lines = "\n".join(f"- {line}" for line in red_ink) if red_ink else "- (none)"
    return f"""# {title}

> Canonical knowledge for this project lives in `pneural-context` under project `{project}`.
> Query it via the pneural-context dashboard or recall API.
> Full backup: `AGENTS.full.md`

## Run / Build

```bash
{run_cmd}
```

## Project-Specific Red Ink

{red_lines}

## See Also

- Engineering standards: `~/.config/opencode/.standards/`
- Infrastructure reference: `pneural-context` project `code-root`
"""


def extract_red_ink(text: str) -> list[str]:
    lines: list[str] = []
    in_red = False
    for line in text.splitlines():
        low = line.lower()
        if any(kw in low for kw in ["critical", "never", "non-negotiable", "forbidden"]):
            in_red = True
        elif line.startswith("## "):
            in_red = False
        if in_red and line.startswith("-"):
            lines.append(line.lstrip("- ").strip())
    return lines[:5]


def slim(path: Path, project: str, dry_run: bool) -> None:
    if not path.exists():
        print(f"skip missing {path}")
        return
    text = path.read_text(encoding="utf-8")
    first_line = text.splitlines()[0].lstrip("# ").strip() if text else project
    backup = path.with_name("AGENTS.full.md")

    # Try to extract a run command
    run_cmd = "see AGENTS.full.md"
    for line in text.splitlines():
        if line.startswith("```bash"):
            run_cmd = "(see AGENTS.full.md for build/run commands)"
            break
        if "npm run" in line or "python " in line or "./" in line:
            run_cmd = line.strip().lstrip("- ").strip()
            if run_cmd:
                break

    red_ink = extract_red_ink(text)
    new_text = pointer_template(first_line, project, run_cmd, red_ink)

    if dry_run:
        print(f"[DRY] {path} -> {backup}")
        return

    backup.write_text(text, encoding="utf-8")
    path.write_text(new_text, encoding="utf-8")
    print(f"slimmed {path} ({len(text)} -> {len(new_text)} chars)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    for path, project in FILES:
        slim(path, project, args.dry_run)


if __name__ == "__main__":
    main()
