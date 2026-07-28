"""unified content engine"""
from alembic import op
import sqlalchemy as sa

revision = "0002_unified_content_engine"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "content_videos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False, unique=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("category", sa.String(100)),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("language", sa.String(16), nullable=False, server_default="pl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_content_videos_public_id", "content_videos", ["public_id"], unique=True)
    op.create_index("ix_content_videos_title", "content_videos", ["title"])
    op.create_index("ix_content_videos_category", "content_videos", ["category"])
    op.create_table(
        "publications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("content_video_id", sa.Integer(), sa.ForeignKey("content_videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform_account_id", sa.Integer(), sa.ForeignKey("platform_accounts.id", ondelete="SET NULL")),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("url", sa.Text()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("platform", "external_id", name="uq_publication_platform_external_id"),
    )
    op.create_index("ix_publications_content_video_id", "publications", ["content_video_id"])
    op.create_index("ix_publications_platform_account_id", "publications", ["platform_account_id"])
    op.create_index("ix_publications_platform", "publications", ["platform"])
    op.create_index("ix_publications_published_at", "publications", ["published_at"])
    op.create_table(
        "metric_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("publication_id", sa.Integer(), sa.ForeignKey("publications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("views", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("reach", sa.BigInteger()),
        sa.Column("impressions", sa.BigInteger()),
        sa.Column("likes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("comments", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("shares", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("saves", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("watch_time_seconds", sa.BigInteger()),
        sa.Column("followers_gained", sa.BigInteger()),
    )
    op.create_index("ix_metric_snapshots_publication_id", "metric_snapshots", ["publication_id"])
    op.create_index("ix_metric_snapshots_captured_at", "metric_snapshots", ["captured_at"])


def downgrade():
    op.drop_table("metric_snapshots")
    op.drop_table("publications")
    op.drop_table("content_videos")
