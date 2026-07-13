from __future__ import annotations

import asyncio
import sys

import click
import asyncpg

from .pb_config import PBConfig
from . import pb_db


def _get_config() -> PBConfig:
    return PBConfig.from_env()


async def _get_pool(config: PBConfig) -> asyncpg.Pool:
    return await asyncpg.create_pool(config.database_url, min_size=1, max_size=5)


@click.group()
def cli():
    pass


@cli.command()
@click.option("--host", default=None, help="Host to bind")
@click.option("--port", default=None, type=int, help="Port to bind")
def serve(host, port):
    from .pb_server import main, config

    if host:
        config.host = host
    if port:
        config.port = port
    main()


@cli.group()
def memory():
    pass


@memory.command("add")
@click.option("--project", "-p", required=True, help="Project name")
@click.option("--text", "-t", required=True, help="Memory text")
@click.option(
    "--priority",
    default="normal",
    type=click.Choice(["critical", "important", "normal"]),
)
@click.option(
    "--type",
    "memory_type",
    default=None,
    type=click.Choice(["red", "concept", "procedural", "temporal", "relation"]),
)
def memory_add(project, text, priority, memory_type):
    async def _run():
        config = _get_config()
        pool = await _get_pool(config)
        pb_db.init_pool(pool)
        entry_id = await pb_db.add_memory_entry(
            project, text, priority, memory_type, pool=pool
        )
        click.echo(f"Added memory entry id={entry_id}")
        await pool.close()

    asyncio.run(_run())


@memory.command("list")
@click.option("--project", "-p", required=True)
def memory_list(project):
    async def _run():
        config = _get_config()
        pool = await _get_pool(config)
        pb_db.init_pool(pool)
        entries = await pb_db.get_memory_entries(project, pool=pool)
        for e in entries:
            click.echo(
                f"[{e['id']}] [{e.get('memory_type', 'temporal')}] [{e.get('priority', 'normal')}] {e['entry'][:100]}"
            )
        click.echo(f"Total: {len(entries)}")
        await pool.close()

    asyncio.run(_run())


@cli.group()
def procedures():
    pass


@procedures.command("list")
@click.option("--project", "-p", required=True)
def proc_list(project):
    async def _run():
        config = _get_config()
        pool = await _get_pool(config)
        pb_db.init_pool(pool)
        procs = await pb_db.list_procedures(project, pool=pool)
        for p in procs:
            click.echo(
                f"[{p['id']}] {p['task_pattern']} (score={p.get('reinforcement_score', 0):.2f})"
            )
        click.echo(f"Total: {len(procs)}")
        await pool.close()

    asyncio.run(_run())


@procedures.command("search")
@click.option("--project", "-p", required=True)
@click.option("--query", "-q", required=True)
def proc_search(project, query):
    async def _run():
        config = _get_config()
        pool = await _get_pool(config)
        pb_db.init_pool(pool)
        results = await pb_db.search_procedures(project, query, pool=pool)
        for r in results:
            click.echo(f"[{r['id']}] {r['task_pattern']} (sim={r.get('sim', 0):.3f})")
        await pool.close()

    asyncio.run(_run())


@cli.command()
@click.option("--project", "-p", required=True)
def consolidation(project):
    async def _run():
        from .pb_engine import run_consolidation
        from .pb_llm import LLMClient

        config = _get_config()
        pool = await _get_pool(config)
        pb_db.init_pool(pool)
        llm = LLMClient(config.llm_url, config.llm_model, config.llm_api_key)
        result = await run_consolidation(project, llm=llm, pool=pool)
        click.echo(str(result))
        await llm.close()
        await pool.close()

    asyncio.run(_run())


@cli.command()
@click.option("--project", "-p", required=True)
def decay(project):
    async def _run():
        config = _get_config()
        pool = await _get_pool(config)
        pb_db.init_pool(pool)
        status = await pb_db.get_decay_status(project, pool=pool)
        click.echo(f"Total entries: {status.get('total', 0)}")
        click.echo(f"Below threshold: {status.get('below_threshold', 0)}")
        await pool.close()

    asyncio.run(_run())


@cli.command()
@click.option("--project", "-p", required=True)
@click.option("--task", "-t", default="")
def briefing(project, task):
    async def _run():
        from .pb_engine import generate_briefing
        from .pb_llm import LLMClient

        config = _get_config()
        pool = await _get_pool(config)
        pb_db.init_pool(pool)
        llm = LLMClient(config.llm_url, config.llm_model, config.llm_api_key)
        result = await generate_briefing(project, task, llm=llm, pool=pool)
        click.echo(result.get("briefing", ""))
        await llm.close()
        await pool.close()

    asyncio.run(_run())


@cli.command()
@click.option("--project", "-p", required=True)
def anchors(project):
    async def _run():
        from .pb_engine import generate_anchors

        config = _get_config()
        pool = await _get_pool(config)
        pb_db.init_pool(pool)
        result = await generate_anchors(project, pool=pool)
        click.echo(f"Active memory: {result.get('active_memory_count', 0)}")
        click.echo(f"Red ink: {result.get('red_ink_count', 0)}")
        click.echo(f"Procedures: {result.get('procedures_count', 0)}")
        await pool.close()

    asyncio.run(_run())


def main():
    cli()


if __name__ == "__main__":
    main()
