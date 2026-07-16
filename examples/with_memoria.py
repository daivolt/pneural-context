import asyncio

import asyncpg

from pneural_context.pb_config import PBConfig
from pneural_context.pb_db import add_memory_entry, get_memory_entries, init_pool
from pneural_context.pb_memoria import MemoriaBridge


async def main():
    config = PBConfig.from_env()
    pool = await asyncpg.create_pool(config.database_url, min_size=2, max_size=10)
    init_pool(pool)

    await add_memory_entry("demo", "Memoria integration enabled", "important")

    if config.memoria_enabled and config.memoria_url:
        bridge = MemoriaBridge(config.memoria_url)
        results = await bridge.recall("memory patterns", project="demo", limit=3)
        print(f"Memoria recall results: {len(results)}")
        await bridge.close()

    entries = await get_memory_entries("demo")
    print(f"Total entries: {len(entries)}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
