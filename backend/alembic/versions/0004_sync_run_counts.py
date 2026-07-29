"""sync run counts"""
from alembic import op
import sqlalchemy as sa

revision = "0004_sync_run_counts"
down_revision = "0003_channel_snapshots"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sync_runs", sa.Column("videos_discovered", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("sync_runs", sa.Column("videos_updated", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("sync_runs", sa.Column("snapshots_created", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("sync_runs", "snapshots_created")
    op.drop_column("sync_runs", "videos_updated")
    op.drop_column("sync_runs", "videos_discovered")
