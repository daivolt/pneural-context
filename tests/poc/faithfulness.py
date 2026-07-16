"""Faithfulness checker — verifies if responses reference seeded memory facts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SEED_DATA_FILE = Path(__file__).parent / "seed_data.json"

FAITHFULNESS_TERMS: dict[int, dict[str, Any]] = {
    1: {
        "terms": ["environment variables", "os.environ", "fail fast", "credentials", "hardcode"],
        "type": "red_ink",
        "description": "Never hardcode database credentials",
    },
    2: {
        "terms": ["pydantic", "validate", "422", "validation"],
        "type": "red_ink",
        "description": "Always validate input with Pydantic models",
    },
    3: {
        "terms": ["asyncpg", "connection pool", "min_size", "pooling"],
        "type": "concept",
        "description": "FastAPI with asyncpg connection pooling",
    },
    4: {
        "terms": ["bloomberg", "type hints", "fail-fast", "generic error", "type hints"],
        "type": "concept",
        "description": "Bloomberg engineering standards",
    },
    5: {
        "terms": ["include_router", "models/", "routers/", "httpx.asynclient", "asyncclient"],
        "type": "procedural",
        "description": "Endpoint creation workflow",
    },
    6: {
        "terms": ["pytest", "httpx", "asynclient", "pytest-asyncio", "coverage"],
        "type": "procedural",
        "description": "Testing conventions",
    },
    7: {
        "terms": ["pagination", "limit", "offset", "page"],
        "type": "temporal",
        "description": "Previous session context about pagination",
    },
    8: {
        "terms": ["user_id", "foreign key", "many-to-one", "belongs to"],
        "type": "relation",
        "description": "Task-User relationship",
    },
}


def check_faithfulness(response: str) -> dict[str, Any]:
    response_lower = response.lower()
    matches: dict[int, dict[str, Any]] = {}

    for seed_id, info in FAITHFULNESS_TERMS.items():
        found_terms = [t for t in info["terms"] if t.lower() in response_lower]
        matches[seed_id] = {
            "seed_id": seed_id,
            "type": info["type"],
            "description": info["description"],
            "found_terms": found_terms,
            "matched": len(found_terms) > 0,
            "match_count": len(found_terms),
        }

    total_seeds = len(FAITHFULNESS_TERMS)
    matched_seeds = sum(1 for m in matches.values() if m["matched"])
    all_terms_found = [t for m in matches.values() if m["matched"] for t in m["found_terms"]]

    return {
        "per_seed": matches,
        "matched_seeds": matched_seeds,
        "total_seeds": total_seeds,
        "match_ratio": round(matched_seeds / total_seeds, 3) if total_seeds > 0 else 0,
        "all_terms_found": all_terms_found,
        "by_type": {
            "red_ink": sum(1 for m in matches.values() if m["type"] == "red_ink" and m["matched"]),
            "concept": sum(1 for m in matches.values() if m["type"] == "concept" and m["matched"]),
            "procedural": sum(
                1 for m in matches.values() if m["type"] == "procedural" and m["matched"]
            ),
            "temporal": sum(
                1 for m in matches.values() if m["type"] == "temporal" and m["matched"]
            ),
            "relation": sum(
                1 for m in matches.values() if m["type"] == "relation" and m["matched"]
            ),
        },
    }


def check_faithfulness_per_turn(responses: list[str]) -> list[dict[str, Any]]:
    results = []
    for i, response in enumerate(responses):
        result = check_faithfulness(response)
        result["turn"] = i + 1
        result["response_length"] = len(response)
        results.append(result)
    return results


def compare_faithfulness(
    control_responses: list[str], treatment_responses: list[str]
) -> dict[str, Any]:
    control_results = check_faithfulness_per_turn(control_responses)
    treatment_results = check_faithfulness_per_turn(treatment_responses)

    control_avg = (
        sum(r["match_ratio"] for r in control_results) / len(control_results)
        if control_results
        else 0
    )
    treatment_avg = (
        sum(r["match_ratio"] for r in treatment_results) / len(treatment_results)
        if treatment_results
        else 0
    )

    per_turn = []
    for c, t in zip(control_results, treatment_results, strict=False):
        per_turn.append(
            {
                "turn": c["turn"],
                "control_matched": c["matched_seeds"],
                "treatment_matched": t["matched_seeds"],
                "control_ratio": c["match_ratio"],
                "treatment_ratio": t["match_ratio"],
                "delta": round(t["match_ratio"] - c["match_ratio"], 3),
                "treatment_terms": t["all_terms_found"],
            }
        )

    return {
        "control_avg_ratio": round(control_avg, 3),
        "treatment_avg_ratio": round(treatment_avg, 3),
        "delta": round(treatment_avg - control_avg, 3),
        "per_turn": per_turn,
        "by_type_control": {
            "red_ink": sum(r["by_type"]["red_ink"] for r in control_results),
            "concept": sum(r["by_type"]["concept"] for r in control_results),
            "procedural": sum(r["by_type"]["procedural"] for r in control_results),
            "temporal": sum(r["by_type"]["temporal"] for r in control_results),
            "relation": sum(r["by_type"]["relation"] for r in control_results),
        },
        "by_type_treatment": {
            "red_ink": sum(r["by_type"]["red_ink"] for r in treatment_results),
            "concept": sum(r["by_type"]["concept"] for r in treatment_results),
            "procedural": sum(r["by_type"]["procedural"] for r in treatment_results),
            "temporal": sum(r["by_type"]["temporal"] for r in treatment_results),
            "relation": sum(r["by_type"]["relation"] for r in treatment_results),
        },
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python faithfulness.py <response_text>")
        sys.exit(1)
    result = check_faithfulness(sys.argv[1])
    print(json.dumps(result, indent=2))
