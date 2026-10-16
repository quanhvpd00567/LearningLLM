"""shopper carts and COD orders"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = '0005_store'
down_revision = '0004_admin'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('shopper_sessions',
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('token_hash')
    )
    op.create_index(op.f('ix_shopper_sessions_expires_at'), 'shopper_sessions', ['expires_at'], unique=False)
    op.create_table('orders',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=20), nullable=False),
    sa.Column('tenant_id', sa.Text(), nullable=False),
    sa.Column('session_hash', sa.String(length=64), nullable=False),
    sa.Column('idempotency_key', sa.Uuid(), nullable=False),
    sa.Column('request_hash', sa.String(length=64), nullable=False),
    sa.Column('customer_name', sa.Text(), nullable=False),
    sa.Column('phone', sa.Text(), nullable=False),
    sa.Column('address', sa.Text(), nullable=False),
    sa.Column('note', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('subtotal', sa.Numeric(precision=18, scale=0), nullable=False),
    sa.Column('shipping_fee', sa.Numeric(precision=14, scale=0), nullable=False),
    sa.Column('total', sa.Numeric(precision=18, scale=0), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('pending','confirmed','shipping','completed','cancelled')", name='ck_order_status'),
    sa.ForeignKeyConstraint(['session_hash'], ['shopper_sessions.token_hash'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code'),
    sa.UniqueConstraint('session_hash', 'idempotency_key', name='uq_order_idempotency')
    )
    op.create_index(op.f('ix_orders_session_hash'), 'orders', ['session_hash'], unique=False)
    op.create_table('cart_items',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('session_hash', sa.String(length=64), nullable=False),
    sa.Column('variant_id', sa.Uuid(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.CheckConstraint('quantity BETWEEN 1 AND 20', name='ck_cart_quantity'),
    sa.ForeignKeyConstraint(['session_hash'], ['shopper_sessions.token_hash'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['variant_id'], ['product_variants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('session_hash', 'variant_id', name='uq_cart_session_variant')
    )
    op.create_index(op.f('ix_cart_items_session_hash'), 'cart_items', ['session_hash'], unique=False)
    op.create_table('order_items',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('order_id', sa.Uuid(), nullable=False),
    sa.Column('variant_id', sa.Uuid(), nullable=True),
    sa.Column('product_name', sa.Text(), nullable=False),
    sa.Column('sku', sa.Text(), nullable=False),
    sa.Column('options', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('unit_price', sa.Numeric(precision=14, scale=0), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['variant_id'], ['product_variants.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_order_items_order_id'), 'order_items', ['order_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_order_items_order_id'), table_name='order_items')
    op.drop_table('order_items')
    op.drop_index(op.f('ix_cart_items_session_hash'), table_name='cart_items')
    op.drop_table('cart_items')
    op.drop_index(op.f('ix_orders_session_hash'), table_name='orders')
    op.drop_table('orders')
    op.drop_index(op.f('ix_shopper_sessions_expires_at'), table_name='shopper_sessions')
    op.drop_table('shopper_sessions')
