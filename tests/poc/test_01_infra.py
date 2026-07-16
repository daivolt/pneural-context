"""Test 01: Infrastructure verification — all services up and configured."""

from __future__ import annotations

import os

import httpx
import pytest

PNEURAL_URL = os.environ.get("PNEURAL_POC_URL", "http://localhost:8779")
LLM_URL = os.environ.get("LLM_URL", "http://localhost:8080")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OPENCODE_URL = os.environ.get("OPENCODE_URL", "http://localhost:4096")


def test_pneural_health(api, tel):
    r = api.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    tel.record("test_01_infra", "pneural_status", data["status"])
    tel.record("test_01_infra", "pneural_version", data.get("version", ""))


def test_pneural_config(api, tel):
    r = api.get("/api/config")
    assert r.status_code == 200
    data = r.json()
    tel.record(
        "test_01_infra",
        "database_configured",
        bool(data.get("database_url") or data.get("database_url_set") is not False),
    )
    tel.record("test_01_infra", "embed_backend", data.get("embed_backend", ""))
    tel.record("test_01_infra", "embed_model", data.get("embed_model", ""))
    tel.record("test_01_infra", "llm_model", data.get("llm_model", ""))


def test_llm_models(tel):
    r = httpx.get(f"{LLM_URL}/v1/models", timeout=10)
    if r.status_code != 200:
        pytest.skip(f"LLM server at {LLM_URL} returned {r.status_code}")
    data = r.json()
    model_ids = [m.get("id", m.get("name", "")) for m in data.get("data", data.get("models", []))]
    tel.record("test_01_infra", "llm_models", model_ids)
    assert any("qwen" in mid.lower() for mid in model_ids), f"No qwen model found in {model_ids}"


def test_ollama_embeddings(tel):
    r = httpx.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": "nomic-embed-text", "prompt": "test"},
        timeout=15,
    )
    if r.status_code != 200:
        pytest.skip(f"Ollama at {OLLAMA_URL} returned {r.status_code}")
    emb = r.json()
    assert "embedding" in emb
    tel.record("test_01_infra", "embed_dim", len(emb["embedding"]))
    tel.record("test_01_infra", "embed_model_verified", "nomic-embed-text")


def test_opencode_serve(oc, tel):
    r = oc.get("/global/health")
    tel.record("test_01_infra", "opencode_serve_status", r.status_code)
    assert r.status_code in (200, 404), f"opencode serve unexpected status: {r.status_code}"


def test_pneural_projects(api, tel):
    r = api.get("/api/projects")
    assert r.status_code == 200
    projects = r.json()
    tel.record("test_01_infra", "existing_projects", projects)
    assert isinstance(projects, list)
