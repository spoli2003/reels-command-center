"""store latest Facebook/Instagram audience count"""

from alembic import op
import sqlalchemy as sa


revision = "0009_platform_audience_count"
down_revision = "0008_meta_platform_integration"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("platform_accounts", sa.Column("audience_count", sa.BigInteger(), nullable=True))


def downgrade():
    op.drop_column("platform_accounts", "audience_count")
