"""channel snapshots"""
from alembic import op
import sqlalchemy as sa

revision = "0003_channel_snapshots"
down_revision = "0002_unified_content_engine"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "youtube_channel_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("youtube_channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("subscriber_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("view_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("video_count", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.create_index("ix_youtube_channel_snapshots_channel_id", "youtube_channel_snapshots", ["channel_id"])
    op.create_index("ix_youtube_channel_snapshots_captured_at", "youtube_channel_snapshots", ["captured_at"])


def downgrade():
    op.drop_table("youtube_channel_snapshots")
