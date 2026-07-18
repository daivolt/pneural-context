"""add_pb_errors

Revision ID: d8e9f1a2b3c4
Revises: 7f2686c2f5df
Create Date: 2026-07-18 17:13:10.132617

"""

from collections.abc import Sequence

from alembic import op

revision: str = "d8e9f1a2b3c4"
down_revision: str | Sequence[str] | None = "7f2686c2f5df"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ERRORS_SQL = """
CREATE TABLE IF NOT EXISTS pb_errors (
    id BIGSERIAL PRIMARY KEY,
    project TEXT NOT NULL,
    session_id TEXT,
    source TEXT NOT NULL DEFAULT 'plugin',
    level TEXT NOT NULL DEFAULT 'error',
    message TEXT NOT NULL,
    stack TEXT,
    created_at DOUBLE PRECISION NOT NULL DEFAULT extract(epoch from now())
);

CREATE INDEX IF NOT EXISTS idx_pb_errors_project ON pb_errors(project);
CREATE INDEX IF NOT EXISTS idx_pb_errors_created ON pb_errors(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pb_errors_level ON pb_errors(level);
"""


def upgrade() -> None:
    op.execute(ERRORS_SQL)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS pb_errors")
