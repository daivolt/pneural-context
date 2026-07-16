import pytest
import asyncio
from pneural_context.pb_config import PBConfig


def test_config_from_env_defaults():
    config = PBConfig.from_env()
    assert config.host == "0.0.0.0"
    assert config.port == 8777
    assert config.decay_interval_seconds == 21600.0
    assert config.archive_threshold == 0.1
    assert config.memoria_enabled is False
    assert config.embed_backend == "ollama"
    assert config.embed_url == "http://localhost:11434"
    assert config.embed_model == "nomic-embed-text"
    assert config.embed_dimensions == 768
    assert config.embed_batch_size == 32
    assert config.dedup_threshold_high == 0.85
    assert config.dedup_threshold_low == 0.55
    assert config.dedup_conversation_messages == 10


def test_config_from_env_override(monkeypatch):
    monkeypatch.setenv("PNEURAL_HOST", "127.0.0.1")
    monkeypatch.setenv("PNEURAL_PORT", "9999")
    monkeypatch.setenv("PNEURAL_DATABASE_URL", "postgresql://test:test@localhost/test")
    config = PBConfig.from_env()
    assert config.host == "127.0.0.1"
    assert config.port == 9999
    assert config.database_url == "postgresql://test:test@localhost/test"


def test_config_embed_env_override(monkeypatch):
    monkeypatch.setenv("PNEURAL_EMBED_BACKEND", "python")
    monkeypatch.setenv("PNEURAL_EMBED_URL", "http://gpu:11434")
    monkeypatch.setenv("PNEURAL_EMBED_MODEL", "bge-m3")
    monkeypatch.setenv("PNEURAL_EMBED_DIMENSIONS", "1024")
    monkeypatch.setenv("PNEURAL_EMBED_BATCH_SIZE", "64")
    monkeypatch.setenv("PNEURAL_DEDUP_THRESHOLD_HIGH", "0.9")
    monkeypatch.setenv("PNEURAL_DEDUP_THRESHOLD_LOW", "0.6")
    monkeypatch.setenv("PNEURAL_DEDUP_CONVERSATION_MESSAGES", "20")
    config = PBConfig.from_env()
    assert config.embed_backend == "python"
    assert config.embed_url == "http://gpu:11434"
    assert config.embed_model == "bge-m3"
    assert config.embed_dimensions == 1024
    assert config.embed_batch_size == 64
    assert config.dedup_threshold_high == 0.9
    assert config.dedup_threshold_low == 0.6
    assert config.dedup_conversation_messages == 20
