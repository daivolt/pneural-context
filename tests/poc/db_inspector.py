"""DB inspector — queries opencode SQLite DB for messages, parts, compaction, and PNEURAL_CTX markers."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def inspect_opencode_db(db_path: Path, session_id: str | None = None) -> dict[str, Any]:
    if not db_path.exists():
        return {"error": f"DB not found at {db_path}"}

    results: dict[str, Any] = {"db_path": str(db_path), "session_id": session_id}
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        results["tables"] = tables

        session_count = conn.execute("SELECT COUNT(*) FROM session").fetchone()[0]
        results["session_count"] = session_count

        if session_count > 0:
            sessions = conn.execute(
                "SELECT id, title, time_created FROM session ORDER BY time_created DESC LIMIT 10"
            ).fetchall()
            results["recent_sessions"] = [dict(r) for r in sessions]

        target_sid = session_id
        if not target_sid and session_count > 0:
            latest = conn.execute(
                "SELECT id FROM session ORDER BY time_created DESC LIMIT 1"
            ).fetchone()
            if latest:
                target_sid = latest[0]
                results["auto_detected_session"] = target_sid

        if target_sid:
            results["session_id_used"] = target_sid

            messages = conn.execute(
                "SELECT id, session_id, time_created, data FROM message "
                "WHERE session_id = ? ORDER BY time_created",
                (target_sid,),
            ).fetchall()
            results["message_count"] = len(messages)
            results["messages"] = []
            for msg_row in messages:
                msg = dict(msg_row)
                if msg.get("data"):
                    try:
                        msg["data_parsed"] = json.loads(msg["data"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                results["messages"].append(msg)

            parts = conn.execute(
                "SELECT id, message_id, session_id, time_created, data FROM part "
                "WHERE session_id = ? ORDER BY time_created",
                (target_sid,),
            ).fetchall()
            results["part_count"] = len(parts)
            results["parts"] = []
            for part_row in parts:
                part = dict(part_row)
                if part.get("data"):
                    try:
                        part["data_parsed"] = json.loads(part["data"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                results["parts"].append(part)

            ctx_found = False
            ctx_locations = []
            all_data_rows = conn.execute(
                "SELECT 'message' AS source, id, data FROM message WHERE session_id = ? "
                "UNION ALL "
                "SELECT 'part' AS source, id, data FROM part WHERE session_id = ? "
                "ORDER BY id",
                (target_sid, target_sid),
            ).fetchall()
            for row in all_data_rows:
                data_str = str(row[2] or "")
                if "PNEURAL_CTX" in data_str:
                    ctx_found = True
                    idx = data_str.index("PNEURAL_CTX")
                    ctx_locations.append(
                        {
                            "source": row[0],
                            "id": row[1],
                            "context_snippet": data_str[idx : idx + 100],
                        }
                    )
            results["pneural_ctx_found_in_db"] = ctx_found
            results["pneural_ctx_locations"] = ctx_locations

            assistant_msgs = conn.execute(
                "SELECT id, data FROM message WHERE session_id = ? " "AND data LIKE '%assistant%'",
                (target_sid,),
            ).fetchall()
            results["assistant_message_count"] = len(assistant_msgs)

            ctx_in_messages = any("PNEURAL_CTX" in str(r[1] or "") for r in assistant_msgs)
            results["marker_in_messages"] = ctx_in_messages

    finally:
        conn.close()

    return results


def compare_dbs(
    control_path: Path,
    treatment_path: Path,
    control_sid: str | None = None,
    treatment_sid: str | None = None,
) -> dict[str, Any]:
    control = inspect_opencode_db(control_path, control_sid)
    treatment = inspect_opencode_db(treatment_path, treatment_sid)

    return {
        "control_ctx_in_db": control.get("pneural_ctx_found_in_db", False),
        "treatment_ctx_in_db": treatment.get("pneural_ctx_found_in_db", False),
        "control_marker_in_messages": control.get("marker_in_messages", False),
        "treatment_marker_in_messages": treatment.get("marker_in_messages", False),
        "control_ctx_locations": control.get("pneural_ctx_locations", []),
        "treatment_ctx_locations": treatment.get("pneural_ctx_locations", []),
        "control_message_count": control.get("message_count", 0),
        "treatment_message_count": treatment.get("message_count", 0),
        "control_part_count": control.get("part_count", 0),
        "treatment_part_count": treatment.get("part_count", 0),
        "control_assistant_messages": control.get("assistant_message_count", 0),
        "treatment_assistant_messages": treatment.get("assistant_message_count", 0),
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python db_inspector.py <db_path> [session_id]")
        print(
            "       python db_inspector.py <control_db> <treatment_db> [control_sid] [treatment_sid]"
        )
        sys.exit(1)

    if len(sys.argv) == 2:
        result = inspect_opencode_db(Path(sys.argv[1]))
    elif len(sys.argv) == 3:
        result = inspect_opencode_db(Path(sys.argv[1]), sys.argv[2])
    elif len(sys.argv) >= 4:
        result = compare_dbs(
            Path(sys.argv[1]),
            Path(sys.argv[2]),
            sys.argv[3] if len(sys.argv) > 3 else None,
            sys.argv[4] if len(sys.argv) > 4 else None,
        )
    else:
        result = {}

    import json

    print(json.dumps(result, indent=2, default=str))
