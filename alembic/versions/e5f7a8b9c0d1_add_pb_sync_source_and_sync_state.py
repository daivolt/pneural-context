"""add_pb_sync_source_and_sync_state

Revision ID: e5f7a8b9c0d1
Revises: d8e9f1a2b3c4
Create Date: 2026-07-22 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "e5f7a8b9c0d1"
down_revision: str | Sequence[str] | None = "d8e9f1a2b3c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


MIGRATION_SQL = """
ALTER TABLE pb_memory ADD COLUMN IF NOT EXISTS pb_sync_source VARCHAR(20) DEFAULT 'local';
CREATE INDEX IF NOT EXISTS idx_pb_memory_sync_source ON pb_memory(pb_sync_source);

CREATE TABLE IF NOT EXISTS pb_sync_state (
    id SERIAL PRIMARY KEY,
    project VARCHAR(200) NOT NULL,
    peer VARCHAR(100) NOT NULL DEFAULT 'memoria',
    last_sync_at DOUBLE PRECISION NOT NULL DEFAULT 0,
    last_sync_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    updated_at DOUBLE PRECISION NOT NULL DEFAULT extract(epoch from now()),
    UNIQUE (project, peer)
);
"""


def upgrade() -> None:
    op.execute(MIGRATION_SQL)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS pb_sync_state")
    op.execute("DROP INDEX IF EXISTS idx_pb_memory_sync_source")
    op.execute("ALTER TABLE pb_memory DROP COLUMN IF EXISTS pb_sync_source")
