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


def test_config_from_env_override(monkeypatch):
    monkeypatch.setenv("PNEURAL_HOST", "127.0.0.1")
    monkeypatch.setenv("PNEURAL_PORT", "9999")
    monkeypatch.setenv("PNEURAL_DATABASE_URL", "postgresql://test:test@localhost/test")
    config = PBConfig.from_env()
    assert config.host == "127.0.0.1"
    assert config.port == 9999
    assert config.database_url == "postgresql://test:test@localhost/test"
