"""Code quality analyzer — checks if treatment responses follow project conventions better than control."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

CONVENTIONS = {
    "type_hints": {
        "patterns": [
            r":\s*(str|int|float|bool|list|dict|tuple|Optional|Union|Any)",
            r"->\s*(str|int|float|bool|list|dict|tuple|Optional|Union|Any|None)",
            r"def\s+\w+\([^)]*:\s*\w+",
        ],
        "weight": 2,
    },
    "error_handling": {
        "patterns": [
            r"raise\s+HTTPException",
            r"except\s+\w+",
            r"try\s*:",
            r"HTTPException\(\s*status_code\s*=",
        ],
        "weight": 2,
    },
    "env_vars": {
        "patterns": [
            r"os\.environ\.get\(",
            r"os\.getenv\(",
            r"environ\[",
            r"environ\.get\(",
        ],
        "weight": 3,
    },
    "pydantic": {
        "patterns": [
            r"BaseModel",
            r"class\s+\w+\(BaseModel\)",
            r"field_validator",
            r"model_validator",
        ],
        "weight": 2,
    },
    "asyncpg": {
        "patterns": [
            r"asyncpg",
            r"create_pool\(",
            r"async\s+def\s+\w+",
            r"await\s+",
        ],
        "weight": 1,
    },
    "fastapi": {
        "patterns": [
            r"APIRouter",
            r"app\.include_router",
            r"Depends\(",
            r"HTTPException",
            r"@router\.",
        ],
        "weight": 2,
    },
    "testing": {
        "patterns": [
            r"pytest",
            r"httpx\.AsyncClient",
            r"test_\w+",
            r"assert\s+",
        ],
        "weight": 1,
    },
    "security": {
        "patterns": [
            r"status_code=422",
            r"status_code=401",
            r"status_code=403",
            r"Validator",
            r"validate",
        ],
        "weight": 2,
    },
}


def analyze_response(text: str) -> dict[str, Any]:
    scores: dict[str, Any] = {}
    total_score = 0
    total_weight = 0

    for conv_name, conv_info in CONVENTIONS.items():
        matches = []
        for pattern in conv_info["patterns"]:
            found = re.findall(pattern, text)
            matches.extend(found)
        unique_matches = list(set(matches))
        score = min(len(unique_matches), 5)
        weighted = score * conv_info["weight"]
        total_score += weighted
        total_weight += 5 * conv_info["weight"]
        scores[conv_name] = {
            "raw_matches": len(matches),
            "unique_matches": len(unique_matches),
            "score_1_5": score,
            "weight": conv_info["weight"],
            "weighted_score": weighted,
        }

    scores["total_weighted_score"] = total_score
    scores["max_possible_score"] = total_weight
    scores["quality_ratio"] = round(total_score / total_weight, 3) if total_weight > 0 else 0
    scores["response_length"] = len(text)
    scores["code_blocks"] = len(re.findall(r"```[\s\S]*?```", text))
    scores["has_imports"] = bool(re.search(r"^import |^from ", text, re.MULTILINE))
    scores["has_class"] = bool(re.search(r"class \w+", text))
    scores["has_function"] = bool(re.search(r"def \w+", text))

    return scores


def analyze_all_turns(responses: list[str]) -> dict[str, Any]:
    per_turn = []
    for i, resp in enumerate(responses):
        scores = analyze_response(resp)
        scores["turn"] = i + 1
        per_turn.append(scores)

    total_scores = {}
    for conv_name in CONVENTIONS:
        scores_list = [t[conv_name]["score_1_5"] for t in per_turn if conv_name in t]
        total_scores[conv_name] = {
            "avg_score": round(sum(scores_list) / len(scores_list), 2) if scores_list else 0,
            "total_matches": sum(t[conv_name]["raw_matches"] for t in per_turn if conv_name in t),
        }

    total_weighted = sum(t["total_weighted_score"] for t in per_turn)
    max_possible = sum(t["max_possible_score"] for t in per_turn)
    overall_ratio = round(total_weighted / max_possible, 3) if max_possible > 0 else 0

    return {
        "per_turn": per_turn,
        "convention_totals": total_scores,
        "overall_weighted_score": total_weighted,
        "overall_max_possible": max_possible,
        "overall_quality_ratio": overall_ratio,
    }


def compare_quality(control_dir: Path, treatment_dir: Path, num_turns: int = 10) -> dict[str, Any]:
    ctrl_responses = []
    treat_responses = []
    for i in range(1, num_turns + 1):
        ctrl_file = control_dir / f"turn_{i:02d}_response.txt"
        treat_file = treatment_dir / f"turn_{i:02d}_response.txt"
        ctrl_responses.append(ctrl_file.read_text() if ctrl_file.exists() else "")
        treat_responses.append(treat_file.read_text() if treat_file.exists() else "")

    ctrl_analysis = analyze_all_turns(ctrl_responses)
    treat_analysis = analyze_all_turns(treat_responses)

    comparison = {
        "control_quality_ratio": ctrl_analysis["overall_quality_ratio"],
        "treatment_quality_ratio": treat_analysis["overall_quality_ratio"],
        "delta": round(
            treat_analysis["overall_quality_ratio"] - ctrl_analysis["overall_quality_ratio"], 3
        ),
        "control_total_weighted": ctrl_analysis["overall_weighted_score"],
        "treatment_total_weighted": treat_analysis["overall_weighted_score"],
        "per_convention_delta": {},
    }

    for conv_name in CONVENTIONS:
        ctrl_avg = ctrl_analysis["convention_totals"].get(conv_name, {}).get("avg_score", 0)
        treat_avg = treat_analysis["convention_totals"].get(conv_name, {}).get("avg_score", 0)
        comparison["per_convention_delta"][conv_name] = round(treat_avg - ctrl_avg, 2)

    return {
        "control": ctrl_analysis,
        "treatment": treat_analysis,
        "comparison": comparison,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python code_quality.py <control_dir> <treatment_dir>")
        sys.exit(1)
    result = compare_quality(Path(sys.argv[1]), Path(sys.argv[2]))
    print(json.dumps(result, indent=2, default=str))
