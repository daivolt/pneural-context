"""LLM Judge — DeepSeek Flash pairwise comparison with position-swapping to eliminate bias."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

CONTROL_LABELS = [("Control", "Treatment"), ("Treatment", "Control")]

JUDGE_SYSTEM_PROMPT = """You are an expert code quality evaluator. You compare two AI assistant responses for the same programming task. Evaluate based on:
1. Faithfulness: Does the response incorporate relevant project conventions and standards from the context?
2. Correctness: Is the code technically correct?
3. Completeness: Does it address all parts of the request?
4. Convention adherence: Does it follow stated project conventions (type hints, error handling, patterns)?

Output JSON only:
{
  "winner": "A" or "B" or "tie",
  "faithfulness_A": 1-5,
  "faithfulness_B": 1-5,
  "correctness_A": 1-5,
  "correctness_B": 1-5,
  "completeness_A": 1-5,
  "completeness_B": 1-5,
  "convention_A": 1-5,
  "convention_B": 1-5,
  "reasoning": "brief explanation"
}"""

JUDGE_USER_TEMPLATE = """Task: {task}

Response A:
{response_a}

Response B:
{response_b}

Which response is better? Evaluate faithfulness, correctness, completeness, and convention adherence."""


def call_deepseek(messages: list[dict], api_key: str, timeout: float = 60.0) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 1024,
    }
    with httpx.Client(timeout=timeout) as client:
        r = client.post(DEEPSEEK_URL, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return {"content": content, "usage": usage}


def parse_judge_response(content: str) -> dict[str, Any]:
    try:
        json_str = content
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0]
        return json.loads(json_str.strip())
    except (json.JSONDecodeError, IndexError):
        return {"raw": content, "parse_error": True}


def judge_pair(
    task: str,
    control_response: str,
    treatment_response: str,
    api_key: str,
) -> dict[str, Any]:
    results: dict[str, Any] = {"task": task[:100]}
    judge_calls = []

    for order_a, order_b in CONTROL_LABELS:
        if order_a == "Control":
            resp_a, resp_b = control_response, treatment_response
        else:
            resp_a, resp_b = treatment_response, control_response

        messages = [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": JUDGE_USER_TEMPLATE.format(
                    task=task, response_a=resp_a[:3000], response_b=resp_b[:3000]
                ),
            },
        ]

        try:
            raw = call_deepseek(messages, api_key)
            parsed = parse_judge_response(raw["content"])

            if order_a == "Control":
                results[f"run_{len(judge_calls) + 1}_order"] = "AB"
                results[f"run_{len(judge_calls) + 1}_winner_raw"] = parsed.get("winner", "unknown")
                if parsed.get("winner") == "A":
                    results[f"run_{len(judge_calls) + 1}_winner_actual"] = "Control"
                elif parsed.get("winner") == "B":
                    results[f"run_{len(judge_calls) + 1}_winner_actual"] = "Treatment"
                else:
                    results[f"run_{len(judge_calls) + 1}_winner_actual"] = "tie"
            else:
                results[f"run_{len(judge_calls) + 1}_order"] = "BA"
                raw_winner = parsed.get("winner", "unknown")
                if raw_winner == "A":
                    results[f"run_{len(judge_calls) + 1}_winner_actual"] = "Treatment"
                elif raw_winner == "B":
                    results[f"run_{len(judge_calls) + 1}_winner_actual"] = "Control"
                else:
                    results[f"run_{len(judge_calls) + 1}_winner_actual"] = "tie"
                results[f"run_{len(judge_calls) + 1}_winner_raw"] = raw_winner

            for metric in ["faithfulness", "correctness", "completeness", "convention"]:
                key_a = f"{metric}_A"
                key_b = f"{metric}_B"
                if order_a == "Control":
                    results.setdefault(f"control_{metric}", []).append(parsed.get(key_a, 0))
                    results.setdefault(f"treatment_{metric}", []).append(parsed.get(key_b, 0))
                else:
                    results.setdefault(f"control_{metric}", []).append(parsed.get(key_b, 0))
                    results.setdefault(f"treatment_{metric}", []).append(parsed.get(key_a, 0))

            results.setdefault("reasoning", []).append(parsed.get("reasoning", ""))
            judge_calls.append(
                {"raw_winner": parsed.get("winner"), "order": f"{order_a}_vs_{order_b}"}
            )
            time.sleep(1)
        except Exception as e:
            results[f"run_{len(judge_calls) + 1}_error"] = str(e)

    votes = []
    for i in range(len(judge_calls)):
        key = f"run_{i + 1}_winner_actual"
        if key in results:
            votes.append(results[key])

    if votes:
        control_wins = votes.count("Control")
        treatment_wins = votes.count("Treatment")
        ties = votes.count("tie")
        results["final_verdict"] = (
            "Treatment"
            if treatment_wins > control_wins
            else "Control"
            if control_wins > treatment_wins
            else "Tie"
        )
        results["control_wins"] = control_wins
        results["treatment_wins"] = treatment_wins
        results["ties"] = ties
    else:
        results["final_verdict"] = "Error"
        results["control_wins"] = 0
        results["treatment_wins"] = 0
        results["ties"] = 0

    for metric in ["faithfulness", "correctness", "completeness", "convention"]:
        ctrl_scores = results.get(f"control_{metric}", [])
        treat_scores = results.get(f"treatment_{metric}", [])
        results[f"avg_control_{metric}"] = (
            round(sum(ctrl_scores) / len(ctrl_scores), 2) if ctrl_scores else 0
        )
        results[f"avg_treatment_{metric}"] = (
            round(sum(treat_scores) / len(treat_scores), 2) if treat_scores else 0
        )

    return results


def judge_all_turns(
    control_responses: list[str],
    treatment_responses: list[str],
    prompts: list[str],
    api_key: str | None = None,
) -> dict[str, Any]:
    if api_key is None:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return {"error": "DEEPSEEK_API_KEY not set", "per_turn": [], "overall_verdict": "Skipped"}

    per_turn = []
    for i, (ctrl, treat, prompt) in enumerate(
        zip(control_responses, treatment_responses, prompts, strict=False)
    ):
        if not ctrl.strip() or not treat.strip():
            per_turn.append({"turn": i + 1, "error": "empty response", "final_verdict": "Skipped"})
            continue
        result = judge_pair(prompt, ctrl, treat, api_key)
        result["turn"] = i + 1
        per_turn.append(result)
        time.sleep(2)

    overall = {
        "control_wins": sum(r.get("control_wins", 0) for r in per_turn if "control_wins" in r),
        "treatment_wins": sum(
            r.get("treatment_wins", 0) for r in per_turn if "treatment_wins" in r
        ),
        "ties": sum(r.get("ties", 0) for r in per_turn if "ties" in r),
    }
    overall["verdict"] = (
        "Treatment"
        if overall["treatment_wins"] > overall["control_wins"]
        else "Control"
        if overall["control_wins"] > overall["treatment_wins"]
        else "Tie"
    )

    metrics = ["faithfulness", "correctness", "completeness", "convention"]
    for m in metrics:
        ctrl_all = [s for r in per_turn for s in r.get(f"control_{m}", [])]
        treat_all = [s for r in per_turn for s in r.get(f"treatment_{m}", [])]
        overall[f"avg_control_{m}"] = round(sum(ctrl_all) / len(ctrl_all), 2) if ctrl_all else 0
        overall[f"avg_treatment_{m}"] = (
            round(sum(treat_all) / len(treat_all), 2) if treat_all else 0
        )

    return {"per_turn": per_turn, "overall": overall}


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python llm_judge.py <control_dir> <treatment_dir> [prompts_file]")
        sys.exit(1)

    ctrl_dir = Path(sys.argv[1])
    treat_dir = Path(sys.argv[2])
    prompts_file = (
        Path(sys.argv[2]).parent / "conversation.json" if len(sys.argv) < 4 else Path(sys.argv[3])
    )

    ctrl_responses = []
    treat_responses = []
    for i in range(1, 11):
        ctrl_file = ctrl_dir / f"turn_{i:02d}_response.txt"
        treat_file = treat_dir / f"turn_{i:02d}_response.txt"
        ctrl_responses.append(ctrl_file.read_text() if ctrl_file.exists() else "")
        treat_responses.append(treat_file.read_text() if treat_file.exists() else "")

    prompts = (
        json.loads(prompts_file.read_text())
        if prompts_file.exists()
        else [f"Turn {i}" for i in range(10)]
    )

    result = judge_all_turns(ctrl_responses, treat_responses, prompts)
    print(json.dumps(result, indent=2, default=str))
