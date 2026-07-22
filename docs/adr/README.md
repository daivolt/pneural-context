# Architecture Decision Records

This directory contains ADRs for pneural-context, following Michael Nygard's format.

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| ADR-0001 | Use asyncpg over SQLAlchemy for performance | Accepted | — |
| ADR-0002 | Use RRF (Reciprocal Rank Fusion) for hybrid text+vector search | Accepted | — |
| ADR-0003 | Use Ebbinghaus-style decay with configurable half-lives | Accepted | — |
| ADR-0004 | Split god modules into routers/ and db/ packages | Accepted | — |
| ADR-0005 | Use Pydantic models for all API request/response validation | Accepted | — |
| ADR-0006 | Use stdlib logging with JSON formatter over structlog | Accepted | — |
| ADR-0007 | Use Alembic for schema migrations over IF NOT EXISTS DDL | Accepted | — |
| ADR-0008 | Use FastAPI dependency injection for testability | Accepted | — |
| ADR-0009 | Memoria-Pneural Context Bridge Architecture | Accepted | 2026-07-22 |
| ADR-0010 | Bidirectional Memory Sync Protocol | Accepted | 2026-07-22 |
| ADR-0011 | Memoria as Episodic Source, Pneural as Injection Consumer | Accepted | 2026-07-22 |
| ADR-0012 | Fix MemoriaBridge Endpoint Paths | Accepted | 2026-07-22 |
| ADR-0013 | Pneural-Context Sync Adapter for Memoria Federation | Accepted | 2026-07-22 |
