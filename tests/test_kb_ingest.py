from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "ingest_agents_md.py"
spec = importlib.util.spec_from_file_location("ingest_agents_md", SCRIPT)
_ingest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_ingest)
classify = _ingest.classify
parse_sections = _ingest.parse_sections


def test_classify_red_ink():
    priority, memory_type = classify("Never do this", "You must never commit secrets.")
    assert priority == "critical"
    assert memory_type == "red"


def test_classify_procedure():
    priority, memory_type = classify("Deploy steps", "1. Build 2. Test 3. Deploy")
    assert priority == "important"
    assert memory_type == "procedural"


def test_classify_relation():
    priority, memory_type = classify("Port reference", "Service runs on port 8080")
    assert memory_type == "relation"


def test_parse_sections_skips_short_bodies(tmp_path: Path):
    path = tmp_path / "AGENTS.md"
    path.write_text("# Project\n\n## Section A\n\nToo short.\n\n## Section B\n\n" + "x" * 50)
    sections = parse_sections(path, "test-project")
    assert len(sections) == 1
    assert sections[0]["header"] == "Section B"
    assert sections[0]["project"] == "test-project"
