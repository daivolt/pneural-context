"""DB inspector — queries opencode SQLite DB for compaction, system messages, PNEURAL_CTX."""

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
                "SELECT id, title, agent, time_created FROM session ORDER BY time_created DESC LIMIT 10"
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

            msgs = conn.execute(
                "SELECT id, type, seq, time_created FROM session_message "
                "WHERE session_id = ? ORDER BY seq",
                (target_sid,),
            ).fetchall()
            results["message_count"] = len(msgs)
            results["message_types"] = {r[1] for r in msgs} if msgs else []

            compaction = conn.execute(
                "SELECT id, type, seq, data FROM session_message "
                "WHERE session_id = ? AND type = 'compaction' ORDER BY seq",
                (target_sid,),
            ).fetchall()
            results["compaction_count"] = len(compaction)
            results["compaction_messages"] = []
            for row in compaction:
                msg = dict(row)
                if msg.get("data"):
                    try:
                        msg["data_parsed"] = json.loads(msg["data"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                results["compaction_messages"].append(msg)

            system_msgs = conn.execute(
                "SELECT id, type, seq, data FROM session_message "
                "WHERE session_id = ? AND type = 'system' ORDER BY seq",
                (target_sid,),
            ).fetchall()
            results["system_message_count"] = len(system_msgs)
            results["system_messages"] = []
            for row in system_msgs:
                msg = dict(row)
                if msg.get("data"):
                    try:
                        msg["data_parsed"] = json.loads(msg["data"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                results["system_messages"].append(msg)

            all_msgs = conn.execute(
                "SELECT id, type, seq, data FROM session_message "
                "WHERE session_id = ? ORDER BY seq",
                (target_sid,),
            ).fetchall()
            ctx_found = False
            ctx_locations = []
            for row in all_msgs:
                data_str = str(row[3] or "")
                if "PNEURAL_CTX" in data_str:
                    ctx_found = True
                    ctx_locations.append(
                        {
                            "id": row[0],
                            "type": row[1],
                            "seq": row[2],
                            "context_snippet": data_str[
                                data_str.index("PNEURAL_CTX") : data_str.index("PNEURAL_CTX") + 100
                            ],
                        }
                    )
            results["pneural_ctx_found_in_db"] = ctx_found
            results["pneural_ctx_locations"] = ctx_locations

            compaction_has_ctx = any("PNEURAL_CTX" in str(r[3] or "") for r in compaction)
            results["marker_in_compaction"] = compaction_has_ctx

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
        "control_compaction_has_ctx": control.get("marker_in_compaction", False),
        "treatment_compaction_has_ctx": treatment.get("marker_in_compaction", False),
        "control_ctx_locations": control.get("pneural_ctx_locations", []),
        "treatment_ctx_locations": treatment.get("pneural_ctx_locations", []),
        "control_message_count": control.get("message_count", 0),
        "treatment_message_count": treatment.get("message_count", 0),
        "control_compaction_count": control.get("compaction_count", 0),
        "treatment_compaction_count": treatment.get("compaction_count", 0),
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
