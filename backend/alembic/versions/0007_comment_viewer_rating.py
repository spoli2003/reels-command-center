"""comment viewer_rating (read-only reflection of the channel's own like status)"""
from alembic import op
import sqlalchemy as sa

revision = "0007_comment_viewer_rating"
down_revision = "0006_youtube_community_inbox"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("youtube_comment_threads", sa.Column("viewer_rating", sa.String(length=16), nullable=True))
    op.add_column("youtube_comments", sa.Column("viewer_rating", sa.String(length=16), nullable=True))


def downgrade():
    op.drop_column("youtube_comments", "viewer_rating")
    op.drop_column("youtube_comment_threads", "viewer_rating")
