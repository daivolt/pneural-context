from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp

logger = logging.getLogger("pneural_context.pb_llm")

CLASSIFY_PROMPT = """Classify this memory entry into one of these types:
- red: critical/warning/important constraint that must never be forgotten
- concept: a learned concept, pattern, or insight
- procedural: a how-to, step-by-step, or process
- temporal: time-sensitive or event-based information
- relation: a relationship between entities or concepts

Memory entry: {text}

Respond with ONLY the type word (red, concept, procedural, temporal, relation)."""

CONSOLIDATE_PROMPT = """Analyze these memory entries and extract key insights, patterns, and consolidated knowledge.

Entries:
{entries}

Return a JSON object with:
- "insights": list of consolidated insights (strings)
- "patterns": list of patterns found (strings)
- "type": overall memory type (concept, procedural, temporal, relation)
- "priority": suggested priority (critical, important, normal)"""

PROCEDURE_EXTRACT_PROMPT = """Given a task and its outcome, extract a reusable procedure.

Task: {task}
Result: {result}

Return a JSON object with:
- "task_pattern": a generalized description of the task type
- "steps": list of steps to complete this task
- "type": task type classification"""


class LLMClient:
    def __init__(self, url: str, model: str = "local-model", api_key: str = ""):
        self.url = url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self._session: aiohttp.ClientSession | None = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _chat(self, messages: list[dict], temperature: float = 0.3) -> str:
        session = await self._ensure_session()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        try:
            async with session.post(
                f"{self.url}/chat/completions", json=payload, headers=headers
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data["choices"][0]["message"]["content"].strip()
        except Exception:
            await self.close()
            raise

    async def classify(self, text: str) -> str:
        prompt = CLASSIFY_PROMPT.format(text=text)
        result = await self._chat([{"role": "user", "content": prompt}])
        result = result.lower().strip()
        valid = {"red", "concept", "procedural", "temporal", "relation"}
        if result in valid:
            return result
        for v in valid:
            if v in result:
                return v
        return "temporal"

    async def consolidate(self, entries: list[dict]) -> dict[str, Any]:
        entries_text = "\n".join(
            f"- [{e.get('memory_type', 'temporal')}] {e.get('entry', '')}"
            for e in entries[:20]
        )
        prompt = CONSOLIDATE_PROMPT.format(entries=entries_text)
        result = await self._chat([{"role": "user", "content": prompt}])
        try:
            text = result
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text.strip())
        except (json.JSONDecodeError, IndexError):
            return {
                "insights": [result],
                "patterns": [],
                "type": "concept",
                "priority": "normal",
            }

    async def extract_procedure(
        self, task: str, result: str = "", steps: list[str] | None = None
    ) -> dict[str, Any]:
        if steps:
            result = "\n".join(f"- {s}" for s in steps)
        prompt = PROCEDURE_EXTRACT_PROMPT.format(task=task, result=result)
        response = await self._chat([{"role": "user", "content": prompt}])
        try:
            text = response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text.strip())
        except (json.JSONDecodeError, IndexError):
            return {
                "task_pattern": task,
                "steps": steps or [result],
                "type": "task",
            }

    async def generate_briefing(self, context: str) -> str:
        prompt = f"""Generate a concise briefing card based on this context:

{context}

Format as a structured briefing with sections: RED INK (critical), Key Concepts, Active Patterns, Procedural Knowledge."""
        return await self._chat([{"role": "user", "content": prompt}])

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
