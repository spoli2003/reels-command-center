"""youtube community inbox (comments, replies, quick reply templates)"""
from alembic import op
import sqlalchemy as sa

revision = "0006_youtube_community_inbox"
down_revision = "0005_sync_run_dedup_and_failures"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sync_runs", sa.Column("threads_discovered", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("sync_runs", sa.Column("comments_imported", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("sync_runs", sa.Column("replies_imported", sa.Integer(), nullable=False, server_default="0"))

    op.create_table(
        "youtube_comment_threads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform_thread_id", sa.String(length=64), nullable=False),
        sa.Column("video_id", sa.Integer(), sa.ForeignKey("youtube_videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("top_level_comment_id", sa.String(length=64), nullable=False),
        sa.Column("author_channel_id", sa.String(length=64), nullable=True),
        sa.Column("author_display_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("author_avatar_url", sa.Text(), nullable=True),
        sa.Column("text_original", sa.Text(), nullable=False, server_default=""),
        sa.Column("like_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_reply_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("moderation_status", sa.String(length=32), nullable=False, server_default="published"),
        sa.Column("can_reply", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("platform_thread_id", name="uq_comment_thread_platform_id"),
    )
    op.create_index("ix_comment_threads_platform_thread_id", "youtube_comment_threads", ["platform_thread_id"])
    op.create_index("ix_comment_threads_video_id", "youtube_comment_threads", ["video_id"])
    op.create_index("ix_comment_threads_top_level_comment_id", "youtube_comment_threads", ["top_level_comment_id"])
    op.create_index("ix_comment_threads_author_channel_id", "youtube_comment_threads", ["author_channel_id"])
    op.create_index("ix_comment_threads_video_published", "youtube_comment_threads", ["video_id", "published_at"])

    op.create_table(
        "youtube_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform_comment_id", sa.String(length=64), nullable=False),
        sa.Column("thread_id", sa.Integer(), sa.ForeignKey("youtube_comment_threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_comment_id", sa.String(length=64), nullable=False),
        sa.Column("author_channel_id", sa.String(length=64), nullable=True),
        sa.Column("author_display_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("author_avatar_url", sa.Text(), nullable=True),
        sa.Column("text_original", sa.Text(), nullable=False, server_default=""),
        sa.Column("like_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_own_reply", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("moderation_status", sa.String(length=32), nullable=False, server_default="published"),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("platform_comment_id", name="uq_comment_platform_id"),
    )
    op.create_index("ix_comments_platform_comment_id", "youtube_comments", ["platform_comment_id"])
    op.create_index("ix_comments_thread_id", "youtube_comments", ["thread_id"])
    op.create_index("ix_comments_parent_comment_id", "youtube_comments", ["parent_comment_id"])
    op.create_index("ix_comments_author_channel_id", "youtube_comments", ["author_channel_id"])
    op.create_index("ix_comments_thread_published", "youtube_comments", ["thread_id", "published_at"])

    op.create_table(
        "quick_reply_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("platform_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_quick_reply_templates_account_id", "quick_reply_templates", ["account_id"])


def downgrade():
    op.drop_index("ix_quick_reply_templates_account_id", table_name="quick_reply_templates")
    op.drop_table("quick_reply_templates")

    op.drop_index("ix_comments_thread_published", table_name="youtube_comments")
    op.drop_index("ix_comments_author_channel_id", table_name="youtube_comments")
    op.drop_index("ix_comments_parent_comment_id", table_name="youtube_comments")
    op.drop_index("ix_comments_thread_id", table_name="youtube_comments")
    op.drop_index("ix_comments_platform_comment_id", table_name="youtube_comments")
    op.drop_table("youtube_comments")

    op.drop_index("ix_comment_threads_video_published", table_name="youtube_comment_threads")
    op.drop_index("ix_comment_threads_author_channel_id", table_name="youtube_comment_threads")
    op.drop_index("ix_comment_threads_top_level_comment_id", table_name="youtube_comment_threads")
    op.drop_index("ix_comment_threads_video_id", table_name="youtube_comment_threads")
    op.drop_index("ix_comment_threads_platform_thread_id", table_name="youtube_comment_threads")
    op.drop_table("youtube_comment_threads")

    op.drop_column("sync_runs", "replies_imported")
    op.drop_column("sync_runs", "comments_imported")
    op.drop_column("sync_runs", "threads_discovered")
