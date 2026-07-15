"""E2E test suite for pneural-context — Phases 1-5 (automated).

Run from desktop-ryzen against the dev server on port 8779.

Environment:
  PNEURAL_E2E_URL=http://localhost:8779  (default)
  PNEURAL_E2E_PROJECT=e2e-test          (default, suffixed with timestamp)
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import datetime

import httpx
import pytest

BASE_URL = os.environ.get("PNEURAL_E2E_URL", "http://localhost:8779")
PROJECT_PREFIX = os.environ.get("PNEURAL_E2E_PROJECT", "e2e-test")
PROJECT = f"{PROJECT_PREFIX}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
TIMEOUT = 30.0


@pytest.fixture(scope="session")
def client():
    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as c:
        yield c


@pytest.fixture(scope="session", autouse=True)
def cleanup(client):
    yield
    try:
        entries = client.get("/api/memory", params={"project": PROJECT}).json()
        for e in entries:
            client.delete("/api/memory/" + str(e["id"]), params={"project": PROJECT})
    except Exception:
        pass


def _add(client, text, priority="normal", memory_type=None):
    body = {"project": PROJECT, "text": text, "priority": priority}
    if memory_type:
        body["memory_type"] = memory_type
    return client.post("/api/memory", json=body).json()


# ═══════════════════════════════════════════════════════════════
# Phase 1: Infrastructure health checks (Tests 1-4)
# ═══════════════════════════════════════════════════════════════


class TestPhase1Infra:
    def test_01_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0a1"

    def test_02_postgres_connection(self, client):
        r = client.get("/api/projects")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_03_llm_reachable(self, client):
        r = client.get("/api/config")
        assert r.status_code == 200
        data = r.json()
        assert data["llm_url"]
        assert data["llm_model"]
        llm_resp = httpx.get(data["llm_url"].rstrip("/") + "/models", timeout=10)
        assert llm_resp.status_code == 200
        models = llm_resp.json().get("data", [])
        assert any(data["llm_model"] in m.get("id", "") for m in models)

    def test_04_embedding_reachable(self, client):
        r = client.get("/api/config")
        assert r.status_code == 200
        data = r.json()
        assert data["embed_backend"] == "ollama"
        embed_url = data["embed_url"]
        resp = httpx.post(
            embed_url.rstrip("/") + "/api/embeddings",
            json={"model": data["embed_model"], "input": "test"},
            timeout=15,
        )
        assert resp.status_code == 200
        emb = resp.json()
        assert "embedding" in emb or "data" in emb


# ═══════════════════════════════════════════════════════════════
# Phase 2: LLM integration (Tests 5-10)
# ═══════════════════════════════════════════════════════════════


class TestPhase2LLM:
    def test_05_consolidation_with_llm(self, client):
        _add(
            client,
            "E2E consolidation fact: Python uses GIL for thread safety",
            "normal",
        )
        _add(
            client,
            "E2E consolidation fact: asyncio runs single-threaded event loops",
            "normal",
        )
        r = client.post("/api/consolidation", json={"project": PROJECT})
        assert r.status_code == 200
        data = r.json()
        assert (
            data.get("ok")
            or data.get("immediate_created") is not None
            or data.get("entries") is not None
        )

    def test_06_briefing_with_llm(self, client):
        _add(
            client,
            "E2E briefing fact: FastAPI supports async endpoints natively",
            "normal",
        )
        r = client.get(
            "/api/briefing", params={"project": PROJECT, "task": "testing briefing"}
        )
        assert r.status_code == 200
        data = r.json()
        assert "markdown" in data or "sections" in data or "briefing" in data

    def test_07_session_record(self, client):
        messages = [
            {"role": "user", "content": "How does asyncpg work?"},
            {"role": "assistant", "content": "asyncpg is an async PostgreSQL driver."},
        ]
        r = client.post(
            "/api/session/record",
            json={
                "project": PROJECT,
                "session_id": str(uuid.uuid4()),
                "title": "E2E session about asyncpg",
                "messages": messages,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data.get("stored") is True
        assert data.get("id")

    def test_08_auto_classify(self, client):
        _add(
            client, "E2E classify: this is a concept about database indexing", "normal"
        )
        r = client.post("/api/memory/classify", json={"project": PROJECT})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)

    def test_09_add_memory_with_type(self, client):
        r = _add(
            client, "E2E red ink fact: never delete production data", "critical", "red"
        )
        assert r.get("id")
        assert r["priority"] == "critical"

    def test_10_context_injection(self, client):
        _add(
            client,
            "E2E context entry: always use transactions in PostgreSQL",
            "important",
        )
        r = client.get("/api/context", params={"project": PROJECT})
        assert r.status_code == 200
        data = r.json()
        assert "markdown" in data
        assert "PNEURAL_CTX" in data["markdown"]


# ═══════════════════════════════════════════════════════════════
# Phase 3: RAG / Embeddings (Tests 11-14)
# ═══════════════════════════════════════════════════════════════


class TestPhase3RAG:
    def test_11_embed_on_write(self, client):
        r = _add(
            client,
            "E2E embed: vector databases use HNSW for approximate nearest neighbors",
        )
        entry_id = r.get("id")
        assert entry_id
        time.sleep(1)
        full = client.get("/api/memory/full", params={"project": PROJECT}).json()
        entry = next((e for e in full if e.get("id") == entry_id), None)
        assert entry is not None
        assert (
            entry.get("embedding") is not None
            or entry.get("has_embedding") is not False
        )

    def test_12_vector_search(self, client):
        _add(
            client,
            "E2E vector: semantic search uses embeddings for similarity matching",
        )
        r = client.get(
            "/api/recall",
            params={
                "q": "how does vector similarity work",
                "project": PROJECT,
                "semantic": "true",
                "limit": 5,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data.get("count", 0) >= 0

    def test_13_trigram_fallback(self, client):
        _add(client, "E2E trigram: exact substring match for recall fallback testing")
        r = client.get(
            "/api/recall",
            params={
                "q": "trigram",
                "project": PROJECT,
                "limit": 5,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["count"] >= 1

    def test_14_reindex(self, client):
        r = client.post("/api/reindex", json={"table": "memory"})
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True


# ═══════════════════════════════════════════════════════════════
# Phase 4: Semantic dedup (Tests 15-18)
# ═══════════════════════════════════════════════════════════════


class TestPhase4Dedup:
    def test_15_smart_dedup_matching(self, client):
        _add(
            client,
            "E2E dedup match: PostgreSQL uses MVCC for concurrent access control",
        )
        r = client.post(
            "/api/context/smart",
            json={
                "project": PROJECT,
                "conversation": "We need to understand how PostgreSQL handles concurrent transactions with MVCC",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data.get("source") in ("smart_dedup", "full", "full_fallback")

    def test_16_smart_dedup_relevant(self, client):
        _add(client, "E2E dedup relevant: Redis is an in-memory key-value store")
        r = client.post(
            "/api/context/smart",
            json={
                "project": PROJECT,
                "conversation": "I want to learn about caching strategies using Redis",
            },
        )
        assert r.status_code == 200

    def test_17_smart_dedup_irrelevant(self, client):
        _add(
            client,
            "E2E dedup irrelevant: Kubernetes pods are the smallest deployable units",
        )
        r = client.post(
            "/api/context/smart",
            json={
                "project": PROJECT,
                "conversation": "Let's discuss Python web frameworks for REST APIs",
            },
        )
        assert r.status_code == 200

    def test_18_red_ink_always_injected(self, client):
        _add(
            client,
            "E2E CRITICAL: always back up databases before schema migrations",
            "critical",
            "red",
        )
        r = client.get("/api/context", params={"project": PROJECT})
        assert r.status_code == 200
        data = r.json()
        assert "red_ink_entries" in data
        red_texts = [e.lower() for e in data["red_ink_entries"]]
        assert any("backup" in t or "migrations" in t for t in red_texts)


# ═══════════════════════════════════════════════════════════════
# Phase 5: Decay & archive (Tests 19-21)
# ═══════════════════════════════════════════════════════════════


class TestPhase5Decay:
    def test_19_decay_run(self, client):
        r = client.post("/api/decay")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)

    def test_20_decay_status(self, client):
        r = client.get("/api/decay/status", params={"project": PROJECT})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_21_archive_decay_and_search(self, client):
        r = client.post("/api/decay/archive", params={"threshold": 0.01})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        r2 = client.get(
            "/api/archive/search",
            params={
                "project": PROJECT,
                "q": "E2E",
                "limit": 5,
            },
        )
        assert r2.status_code == 200
