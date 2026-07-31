"""Meta platform integration: content thumbnail and generic comment tables."""

from alembic import op
import sqlalchemy as sa

revision = "0008_meta_platform_integration"
down_revision = "0007_comment_viewer_rating"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("content_videos", sa.Column("thumbnail_url", sa.Text(), nullable=True))

    op.create_table(
        "content_comment_threads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("platform_thread_id", sa.String(length=128), nullable=False),
        sa.Column("publication_id", sa.Integer(), sa.ForeignKey("publications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("top_level_comment_id", sa.String(length=128), nullable=False),
        sa.Column("author_external_id", sa.String(length=128), nullable=True),
        sa.Column("author_display_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("author_avatar_url", sa.Text(), nullable=True),
        sa.Column("text_original", sa.Text(), nullable=False, server_default=""),
        sa.Column("like_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_reply_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("can_reply", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("platform_thread_id", name="uq_content_comment_thread_platform_id"),
    )
    op.create_index("ix_content_comment_threads_platform", "content_comment_threads", ["platform"])
    op.create_index("ix_content_comment_threads_platform_thread_id", "content_comment_threads", ["platform_thread_id"])
    op.create_index("ix_content_comment_threads_publication_id", "content_comment_threads", ["publication_id"])
    op.create_index("ix_content_comment_threads_top_level_comment_id", "content_comment_threads", ["top_level_comment_id"])
    op.create_index("ix_content_comment_threads_author_external_id", "content_comment_threads", ["author_external_id"])
    op.create_index("ix_content_comment_threads_publication_published", "content_comment_threads", ["publication_id", "published_at"])

    op.create_table(
        "content_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("platform_comment_id", sa.String(length=128), nullable=False),
        sa.Column("thread_id", sa.Integer(), sa.ForeignKey("content_comment_threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_comment_id", sa.String(length=128), nullable=False),
        sa.Column("author_external_id", sa.String(length=128), nullable=True),
        sa.Column("author_display_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("author_avatar_url", sa.Text(), nullable=True),
        sa.Column("text_original", sa.Text(), nullable=False, server_default=""),
        sa.Column("like_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_own_reply", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("platform_comment_id", name="uq_content_comment_platform_id"),
    )
    op.create_index("ix_content_comments_platform", "content_comments", ["platform"])
    op.create_index("ix_content_comments_platform_comment_id", "content_comments", ["platform_comment_id"])
    op.create_index("ix_content_comments_thread_id", "content_comments", ["thread_id"])
    op.create_index("ix_content_comments_parent_comment_id", "content_comments", ["parent_comment_id"])
    op.create_index("ix_content_comments_author_external_id", "content_comments", ["author_external_id"])
    op.create_index("ix_content_comments_thread_published", "content_comments", ["thread_id", "published_at"])


def downgrade():
    op.drop_index("ix_content_comments_thread_published", table_name="content_comments")
    op.drop_index("ix_content_comments_author_external_id", table_name="content_comments")
    op.drop_index("ix_content_comments_parent_comment_id", table_name="content_comments")
    op.drop_index("ix_content_comments_thread_id", table_name="content_comments")
    op.drop_index("ix_content_comments_platform_comment_id", table_name="content_comments")
    op.drop_index("ix_content_comments_platform", table_name="content_comments")
    op.drop_table("content_comments")

    op.drop_index("ix_content_comment_threads_publication_published", table_name="content_comment_threads")
    op.drop_index("ix_content_comment_threads_author_external_id", table_name="content_comment_threads")
    op.drop_index("ix_content_comment_threads_top_level_comment_id", table_name="content_comment_threads")
    op.drop_index("ix_content_comment_threads_publication_id", table_name="content_comment_threads")
    op.drop_index("ix_content_comment_threads_platform_thread_id", table_name="content_comment_threads")
    op.drop_index("ix_content_comment_threads_platform", table_name="content_comment_threads")
    op.drop_table("content_comment_threads")

    op.drop_column("content_videos", "thumbnail_url")
