"""initial schema"""
from alembic import op
import sqlalchemy as sa
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("users", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("email", sa.String(320), nullable=False), sa.Column("full_name", sa.String(255), nullable=False), sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("email"))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("reels", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("title", sa.String(255), nullable=False), sa.Column("category", sa.String(100), nullable=False), sa.Column("hook", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_reels_title", "reels", ["title"]); op.create_index("ix_reels_category", "reels", ["category"])
    op.create_table("platform_accounts", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("platform", sa.String(32), nullable=False), sa.Column("external_account_id", sa.String(255), nullable=False), sa.Column("display_name", sa.String(255), nullable=False), sa.Column("access_token_encrypted", sa.Text(), nullable=False), sa.Column("refresh_token_encrypted", sa.Text()), sa.Column("token_expires_at", sa.DateTime(timezone=True)), sa.Column("scopes", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("platform","external_account_id", name="uq_platform_external_account"))
    op.create_table("youtube_channels", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("account_id", sa.Integer(), sa.ForeignKey("platform_accounts.id", ondelete="CASCADE"), nullable=False), sa.Column("youtube_channel_id", sa.String(64), nullable=False, unique=True), sa.Column("title", sa.String(255), nullable=False), sa.Column("uploads_playlist_id", sa.String(64), nullable=False), sa.Column("subscriber_count", sa.BigInteger(), nullable=False), sa.Column("view_count", sa.BigInteger(), nullable=False), sa.Column("video_count", sa.BigInteger(), nullable=False), sa.Column("thumbnail_url", sa.Text()), sa.Column("synced_at", sa.DateTime(timezone=True)))
    op.create_table("youtube_videos", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("channel_id", sa.Integer(), sa.ForeignKey("youtube_channels.id", ondelete="CASCADE"), nullable=False), sa.Column("youtube_video_id", sa.String(32), nullable=False, unique=True), sa.Column("title", sa.String(500), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("published_at", sa.DateTime(timezone=True), nullable=False), sa.Column("thumbnail_url", sa.Text()), sa.Column("duration_seconds", sa.Integer()), sa.Column("is_short_candidate", sa.Boolean(), nullable=False))
    op.create_table("youtube_metric_snapshots", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("video_id", sa.Integer(), sa.ForeignKey("youtube_videos.id", ondelete="CASCADE"), nullable=False), sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False), sa.Column("views", sa.BigInteger(), nullable=False), sa.Column("likes", sa.BigInteger(), nullable=False), sa.Column("comments", sa.BigInteger(), nullable=False))
    op.create_table("sync_runs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("platform", sa.String(32), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("finished_at", sa.DateTime(timezone=True)), sa.Column("imported_items", sa.Integer(), nullable=False), sa.Column("error_message", sa.Text()))

def downgrade():
    for table in ["sync_runs","youtube_metric_snapshots","youtube_videos","youtube_channels","platform_accounts","reels","users"]: op.drop_table(table)
