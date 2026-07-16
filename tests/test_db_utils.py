from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pneural_context.db import utils as utils_mod


@pytest.fixture(autouse=True)
def setup_pool(mock_pool):
    from pneural_context import pb_db

    pb_db.init_pool(mock_pool)
    yield
    pb_db.init_pool(None)


@pytest.mark.asyncio
async def test_get_all_projects(mock_pool):
    mock_pool.fetch = AsyncMock(
        return_value=[
            {"project": "alpha"},
            {"project": "beta"},
        ]
    )
    result = await utils_mod.get_all_projects(pool=mock_pool)
    assert result == ["alpha", "beta"]


@pytest.mark.asyncio
async def test_get_all_projects_empty(mock_pool):
    mock_pool.fetch = AsyncMock(return_value=[])
    result = await utils_mod.get_all_projects(pool=mock_pool)
    assert result == []
