"""Log inspector — parses llama.cpp logs for PNEURAL_CTX marker and system prompt content."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def parse_llama_log(log_path: Path) -> dict[str, Any]:
    if not log_path.exists():
        return {"error": f"Log file not found: {log_path}"}

    text = log_path.read_text(errors="replace")
    lines = text.splitlines()

    results: dict[str, Any] = {
        "log_file": str(log_path),
        "total_lines": len(lines),
        "pneural_ctx_occurrences": 0,
        "pneural_ctx_line_numbers": [],
        "system_prompt_found": False,
        "system_prompt_line_numbers": [],
        "injected_entries_found": [],
        "prompt_blocks": [],
    }

    ctx_pattern = re.compile(r"PNEURAL_CTX")

    in_prompt_block = False
    prompt_block_lines: list[str] = []
    prompt_block_start = 0

    for i, line in enumerate(lines):
        if ctx_pattern.search(line):
            results["pneural_ctx_occurrences"] += 1
            results["pneural_ctx_line_numbers"].append(i + 1)

        if "<!-- PNEURAL_CTX:" in line or "PNEURAL_CTX:" in line:
            marker_match = re.search(r"PNEURAL_CTX:\s*(\w+)", line)
            if marker_match:
                results["marker_value"] = marker_match.group(1)

        if (
            "system" in line.lower()
            and ("prompt" in line.lower() or "role" in line.lower())
            and not results["system_prompt_found"]
        ):
            results["system_prompt_found"] = True
            results["system_prompt_line_numbers"].append(i + 1)

        for entry_text in [
            "environment variables",
            "os.environ",
            "asyncpg",
            "connection pool",
            "Pydantic",
            "Bloomberg",
            "fail-fast",
            "repository pattern",
            "httpx.AsyncClient",
            "pytest",
            "user_id",
            "foreign key",
            "422",
            "CRITICAL",
            "Red Ink",
        ]:
            if (
                entry_text.lower() in line.lower()
                and entry_text not in results["injected_entries_found"]
            ):
                results["injected_entries_found"].append(entry_text)

        if "prompt" in line.lower() and "token" in line.lower():
            if not in_prompt_block:
                in_prompt_block = True
                prompt_block_start = i + 1
                prompt_block_lines = [line]
            else:
                prompt_block_lines.append(line)
        elif in_prompt_block:
            if len(prompt_block_lines) > 5:
                results["prompt_blocks"].append(
                    {
                        "start_line": prompt_block_start,
                        "end_line": i,
                        "line_count": len(prompt_block_lines),
                        "has_ctx_marker": any("PNEURAL_CTX" in line for line in prompt_block_lines),
                    }
                )
            in_prompt_block = False
            prompt_block_lines = []

    results["pneural_ctx_present"] = results["pneural_ctx_occurrences"] > 0

    if "marker_value" not in results and results["pneural_ctx_occurrences"] > 0:
        for line_num in results["pneural_ctx_line_numbers"][:5]:
            line = lines[line_num - 1] if line_num <= len(lines) else ""
            marker_match = re.search(r"PNEURAL_CTX:\s*(\w+)", line)
            if marker_match:
                results["marker_value"] = marker_match.group(1)
                break

    return results


def compare_logs(control_path: Path, treatment_path: Path) -> dict[str, Any]:
    control = parse_llama_log(control_path)
    treatment = parse_llama_log(treatment_path)

    return {
        "control_has_ctx": control.get("pneural_ctx_present", False),
        "treatment_has_ctx": treatment.get("pneural_ctx_present", False),
        "control_ctx_count": control.get("pneural_ctx_occurrences", 0),
        "treatment_ctx_count": treatment.get("pneural_ctx_occurrences", 0),
        "treatment_marker": treatment.get("marker_value"),
        "treatment_entries_found": treatment.get("injected_entries_found", []),
        "control_entries_found": control.get("injected_entries_found", []),
        "control_prompt_blocks_with_ctx": sum(
            1 for b in control.get("prompt_blocks", []) if b.get("has_ctx_marker")
        ),
        "treatment_prompt_blocks_with_ctx": sum(
            1 for b in treatment.get("prompt_blocks", []) if b.get("has_ctx_marker")
        ),
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python log_inspector.py <log_file> [control_log treatment_log]")
        sys.exit(1)

    if len(sys.argv) == 2:
        result = parse_llama_log(Path(sys.argv[1]))
    else:
        result = compare_logs(Path(sys.argv[1]), Path(sys.argv[2]))

    import json

    print(json.dumps(result, indent=2, default=str))
