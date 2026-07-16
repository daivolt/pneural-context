from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pneural_context.db.pool import _get_pool, init_embedding_client, init_pool


def test_init_pool():
    mock_pool = AsyncMock()
    init_pool(mock_pool)
    from pneural_context.db import pool as pool_mod

    assert pool_mod._pool is mock_pool


def test_init_embedding_client():
    from pneural_context.db import pool as pool_mod

    init_embedding_client(None)
    assert pool_mod._embedding_client is None


@pytest.mark.asyncio
async def test_get_pool_with_explicit_pool():
    mock_pool = AsyncMock()
    result = await _get_pool(mock_pool)
    assert result is mock_pool


@pytest.mark.asyncio
async def test_get_pool_from_module():
    from pneural_context.db import pool as pool_mod

    mock_pool = AsyncMock()
    pool_mod._pool = mock_pool
    result = await _get_pool(None)
    assert result is mock_pool


@pytest.mark.asyncio
async def test_get_pool_raises_without_init():
    from pneural_context.db import pool as pool_mod

    pool_mod._pool = None
    with pytest.raises(RuntimeError, match="Database pool not initialized"):
        await _get_pool(None)
