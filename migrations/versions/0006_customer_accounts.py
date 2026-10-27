"""Customer accounts with stable private cart/order ownership and revocable sessions."""
from alembic import op
import sqlalchemy as sa

revision = "0006_customers"
down_revision = "0005_store"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("customers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("owner_hash", sa.String(64), sa.ForeignKey("shopper_sessions.token_hash"), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "email", name="uq_customer_tenant_email"))
    op.create_table("customer_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_customer_sessions_customer_id", "customer_sessions", ["customer_id"])
    op.create_index("ix_customer_sessions_expires_at", "customer_sessions", ["expires_at"])
    op.create_table("customer_auth_limits",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_customer_auth_limits_expires_at", "customer_auth_limits", ["expires_at"])


def downgrade():
    op.drop_table("customer_auth_limits")
    op.drop_table("customer_sessions")
    op.drop_table("customers")
