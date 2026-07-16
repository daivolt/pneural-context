-- pneural-context PostgreSQL Schema
-- All table names use pb_ prefix

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- pb_memory: per-project memory entries
CREATE TABLE IF NOT EXISTS pb_memory (
    id                  BIGSERIAL PRIMARY KEY,
    project             TEXT NOT NULL,
    entry               TEXT NOT NULL,
    priority            VARCHAR(10) NOT NULL DEFAULT 'normal',
    memory_type         VARCHAR(20) NOT NULL DEFAULT 'temporal',
    strength            DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    last_accessed       DOUBLE PRECISION NOT NULL DEFAULT extract(epoch from now()),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    search_enrichments  TEXT[] NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_pb_memory_project ON pb_memory(project);
CREATE INDEX IF NOT EXISTS idx_pb_memory_entry_trgm ON pb_memory USING gin (entry gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_pb_memory_priority ON pb_memory(priority);
CREATE INDEX IF NOT EXISTS idx_pb_memory_type ON pb_memory(memory_type);
CREATE INDEX IF NOT EXISTS idx_pb_memory_strength ON pb_memory(strength);
CREATE INDEX IF NOT EXISTS idx_pb_memory_last_accessed ON pb_memory(last_accessed);
CREATE INDEX IF NOT EXISTS idx_pb_memory_project_priority ON pb_memory(project, priority);
CREATE INDEX IF NOT EXISTS idx_pb_memory_project_type ON pb_memory(project, memory_type);
CREATE INDEX IF NOT EXISTS idx_pb_memory_project_type_created ON pb_memory(project, memory_type, created_at);
CREATE INDEX IF NOT EXISTS idx_pb_memory_enrich ON pb_memory USING gin (search_enrichments);

ALTER TABLE pb_memory DROP CONSTRAINT IF EXISTS chk_pb_memory_priority;
ALTER TABLE pb_memory ADD CONSTRAINT chk_pb_memory_priority
    CHECK (priority IN ('critical', 'important', 'normal'));

ALTER TABLE pb_memory DROP CONSTRAINT IF EXISTS chk_pb_memory_type;
ALTER TABLE pb_memory ADD CONSTRAINT chk_pb_memory_type
    CHECK (memory_type IN ('red', 'concept', 'procedural', 'temporal', 'relation'));

ALTER TABLE pb_memory ADD COLUMN IF NOT EXISTS embedding vector(768);
CREATE INDEX IF NOT EXISTS idx_pb_memory_embedding ON pb_memory USING hnsw (embedding vector_cosine_ops);

-- pb_procedural_memory: basal ganglia procedural memory
CREATE TABLE IF NOT EXISTS pb_procedural_memory (
    id SERIAL PRIMARY KEY,
    project VARCHAR(200) NOT NULL,
    task_pattern VARCHAR(500) NOT NULL,
    task_type VARCHAR(100),
    steps JSONB NOT NULL DEFAULT '[]',
    success_count INTEGER NOT NULL DEFAULT 0,
    fail_count INTEGER NOT NULL DEFAULT 0,
    reinforcement_score DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    last_success_at DOUBLE PRECISION,
    proven_by TEXT[] NOT NULL DEFAULT '{}',
    created_at DOUBLE PRECISION NOT NULL DEFAULT extract(epoch from now()),
    retired BOOLEAN NOT NULL DEFAULT FALSE,
    search_enrichments TEXT[] NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_pb_proc_project ON pb_procedural_memory(project);
CREATE INDEX IF NOT EXISTS idx_pb_proc_pattern ON pb_procedural_memory USING gin (task_pattern gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_pb_proc_score ON pb_procedural_memory(reinforcement_score DESC);
CREATE INDEX IF NOT EXISTS idx_pb_proc_retired ON pb_procedural_memory(retired);

ALTER TABLE pb_procedural_memory DROP CONSTRAINT IF EXISTS chk_pb_proc_score_range;
ALTER TABLE pb_procedural_memory ADD CONSTRAINT chk_pb_proc_score_range
    CHECK (reinforcement_score >= 0 AND reinforcement_score <= 1);

ALTER TABLE pb_procedural_memory DROP CONSTRAINT IF EXISTS chk_pb_proc_counts_nonneg;
ALTER TABLE pb_procedural_memory ADD CONSTRAINT chk_pb_proc_counts_nonneg
    CHECK (success_count >= 0 AND fail_count >= 0);

ALTER TABLE pb_procedural_memory ADD COLUMN IF NOT EXISTS embedding vector(768);
CREATE INDEX IF NOT EXISTS idx_pb_proc_embedding ON pb_procedural_memory USING hnsw (embedding vector_cosine_ops);

-- pb_consolidated_memory: 3-tier cortex consolidation
CREATE TABLE IF NOT EXISTS pb_consolidated_memory (
    id SERIAL PRIMARY KEY,
    project VARCHAR(200) NOT NULL,
    tier VARCHAR(20) NOT NULL DEFAULT 'consolidated',
    content TEXT NOT NULL,
    source_sessions TEXT[] NOT NULL DEFAULT '{}',
    source_episode_ids TEXT[] NOT NULL DEFAULT '{}',
    memory_type VARCHAR(20) NOT NULL DEFAULT 'concept',
    priority VARCHAR(10) NOT NULL DEFAULT 'normal',
    strength DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    created_at DOUBLE PRECISION NOT NULL DEFAULT extract(epoch from now()),
    last_accessed DOUBLE PRECISION NOT NULL DEFAULT extract(epoch from now()),
    search_enrichments TEXT[] NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_pb_consol_project_tier ON pb_consolidated_memory(project, tier);
CREATE INDEX IF NOT EXISTS idx_pb_consol_priority ON pb_consolidated_memory(priority);
CREATE INDEX IF NOT EXISTS idx_pb_consol_type ON pb_consolidated_memory(memory_type);
CREATE INDEX IF NOT EXISTS idx_pb_consol_last_accessed ON pb_consolidated_memory(last_accessed);
CREATE INDEX IF NOT EXISTS idx_pb_consol_strength ON pb_consolidated_memory(strength);

ALTER TABLE pb_consolidated_memory DROP CONSTRAINT IF EXISTS chk_pb_consol_priority;
ALTER TABLE pb_consolidated_memory ADD CONSTRAINT chk_pb_consol_priority
    CHECK (priority IN ('critical', 'important', 'normal'));

ALTER TABLE pb_consolidated_memory DROP CONSTRAINT IF EXISTS chk_pb_consol_memory_type;
ALTER TABLE pb_consolidated_memory ADD CONSTRAINT chk_pb_consol_memory_type
    CHECK (memory_type IN ('red', 'concept', 'procedural', 'temporal', 'relation'));

ALTER TABLE pb_consolidated_memory DROP CONSTRAINT IF EXISTS chk_pb_consol_tier;
ALTER TABLE pb_consolidated_memory ADD CONSTRAINT chk_pb_consol_tier
    CHECK (tier IN ('immediate', 'consolidated', 'timeless'));

ALTER TABLE pb_consolidated_memory ADD COLUMN IF NOT EXISTS embedding vector(768);
CREATE INDEX IF NOT EXISTS idx_pb_consol_embedding ON pb_consolidated_memory USING hnsw (embedding vector_cosine_ops);

-- pb_memory_archive: forgotten but searchable
CREATE TABLE IF NOT EXISTS pb_memory_archive (
    id BIGSERIAL PRIMARY KEY,
    original_id BIGINT NOT NULL,
    project TEXT NOT NULL,
    entry TEXT NOT NULL,
    priority VARCHAR(10) NOT NULL DEFAULT 'normal',
    memory_type VARCHAR(20) NOT NULL DEFAULT 'temporal',
    strength DOUBLE PRECISION NOT NULL DEFAULT 0.1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at DOUBLE PRECISION NOT NULL DEFAULT extract(epoch from now()),
    search_enrichments TEXT[] NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_pb_archive_project ON pb_memory_archive(project);
CREATE INDEX IF NOT EXISTS idx_pb_archive_type ON pb_memory_archive(memory_type);

-- pb_memory_costs: token cost analytics
CREATE TABLE IF NOT EXISTS pb_memory_costs (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(100),
    project VARCHAR(200) NOT NULL,
    tokens_injected INTEGER NOT NULL DEFAULT 0,
    tokens_saved_injection INTEGER NOT NULL DEFAULT 0,
    tokens_saved_forgetting INTEGER NOT NULL DEFAULT 0,
    context_type VARCHAR(20) NOT NULL DEFAULT 'full',
    task_outcome VARCHAR(20),
    created_at DOUBLE PRECISION NOT NULL DEFAULT extract(epoch from now()),
    breakdown JSONB
);

CREATE INDEX IF NOT EXISTS idx_pb_costs_project ON pb_memory_costs(project);
CREATE INDEX IF NOT EXISTS idx_pb_costs_created ON pb_memory_costs(created_at);

-- pb_papers: research paper index
CREATE TABLE IF NOT EXISTS pb_papers (
    id BIGSERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    folder TEXT NOT NULL DEFAULT 'papers',
    title TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL DEFAULT '',
    enriched_text TEXT NOT NULL DEFAULT '',
    file_mtime DOUBLE PRECISION NOT NULL DEFAULT 0,
    indexed_at DOUBLE PRECISION NOT NULL DEFAULT extract(epoch from now()),
    UNIQUE (filename, folder)
);

CREATE INDEX IF NOT EXISTS idx_pb_papers_filename ON pb_papers(filename);
CREATE INDEX IF NOT EXISTS idx_pb_papers_folder ON pb_papers(folder);
CREATE INDEX IF NOT EXISTS idx_pb_papers_text_trgm ON pb_papers USING gin (text gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_pb_papers_enriched_trgm ON pb_papers USING gin (enriched_text gin_trgm_ops);

ALTER TABLE pb_papers ADD COLUMN IF NOT EXISTS embedding vector(768);
CREATE INDEX IF NOT EXISTS idx_pb_papers_embedding ON pb_papers USING hnsw (embedding vector_cosine_ops);