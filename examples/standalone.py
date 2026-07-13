import asyncio
from pneural_context.pb_config import PBConfig
from pneural_context.pb_db import init_pool, add_memory_entry, get_memory_entries
import asyncpg


async def main():
    config = PBConfig.from_env()
    pool = await asyncpg.create_pool(config.database_url, min_size=2, max_size=10)
    init_pool(pool)

    entry_id = await add_memory_entry(
        "demo", "Always use pb_ prefix for table names", "critical"
    )
    print(f"Added entry: {entry_id}")

    entries = await get_memory_entries("demo")
    for e in entries:
        print(f"  [{e['id']}] {e['entry']}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
