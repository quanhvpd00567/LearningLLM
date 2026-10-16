"""admin settings and sessions"""
from alembic import op
import sqlalchemy as sa

revision = '0004_admin'
down_revision = '0003_worker_chunks'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('admin_sessions',
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('username', sa.Text(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('token_hash')
    )
    op.create_index(op.f('ix_admin_sessions_expires_at'), 'admin_sessions', ['expires_at'], unique=False)
    op.create_table('admin_settings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('shop_name', sa.Text(), nullable=False),
    sa.Column('contact_email', sa.Text(), nullable=False),
    sa.Column('low_stock_threshold', sa.Integer(), nullable=False),
    sa.Column('embedding_paused', sa.Boolean(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('id = 1', name='ck_admin_settings_singleton'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('admin_settings')
    op.drop_index(op.f('ix_admin_sessions_expires_at'), table_name='admin_sessions')
    op.drop_table('admin_sessions')
