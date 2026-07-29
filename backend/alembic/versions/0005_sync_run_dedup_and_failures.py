"""sync run dedup and per-video failure counts"""
from alembic import op
import sqlalchemy as sa

revision = "0005_sync_run_dedup_and_failures"
down_revision = "0004_sync_run_counts"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sync_runs", sa.Column("snapshots_deduplicated", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("sync_runs", sa.Column("videos_failed", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("sync_runs", "videos_failed")
    op.drop_column("sync_runs", "snapshots_deduplicated")
