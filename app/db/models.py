from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("source_type", "document_id", "source_version", "embedding_model", "pipeline_version", "chunk_index", name="uq_chunk_source_profile"),
        CheckConstraint("status IN ('current', 'archived', 'deleted')", name="document_chunks_status_check"),
        Index("idx_document_chunks_tenant", "tenant_id"),
        Index("idx_document_chunks_document", "document_id"),
        Index("idx_document_chunks_status", "status"),
        Index("idx_document_chunks_metadata", "metadata", postgresql_using="gin"),
        Index("idx_document_chunks_embedding_hnsw", "embedding", postgresql_using="hnsw",
              postgresql_ops={"embedding": "vector_cosine_ops"},
              postgresql_with={"m": 16, "ef_construction": 64}),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    document_id: Mapped[UUID]
    # Nullable for compatibility with legacy chunks. Worker-populated fields.
    source_type: Mapped[str | None] = mapped_column(Text)
    source_version: Mapped[int | None] = mapped_column(Integer)
    embedding_model: Mapped[str | None] = mapped_column(Text)
    pipeline_version: Mapped[int | None] = mapped_column(Integer)
    chunk_index: Mapped[int | None] = mapped_column(Integer)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))
    tenant_id: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(Text, server_default="vi")
    status: Mapped[str] = mapped_column(Text, server_default="current")
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# Ecommerce source data; prices are stored as whole VND.


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(String(120), unique=True)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (CheckConstraint("source_version >= 1", name="ck_product_version"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    category_id: Mapped[UUID] = mapped_column(ForeignKey("categories.id"))
    tenant_id: Mapped[str] = mapped_column(Text, default="demo")
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    source_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_variant_price"),
        CheckConstraint("stock >= 0", name="ck_variant_stock"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id"), index=True)
    sku: Mapped[str] = mapped_column(String(120), unique=True)
    options: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    price: Mapped[Decimal] = mapped_column(Numeric(14, 0))
    stock: Mapped[int] = mapped_column(Integer)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (CheckConstraint("source_version >= 1", name="ck_knowledge_version"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(Text, default="demo")
    title: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    source_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", "source_version", "job_type", "embedding_model", "pipeline_version", name="uq_job_source_profile"),
        CheckConstraint("source_type IN ('product', 'knowledge')", name="ck_job_source_type"),
        CheckConstraint("job_type IN ('embed_source', 'delete_source_embeddings')", name="ck_job_type"),
        CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed', 'superseded')", name="ck_job_status"),
        CheckConstraint("attempts >= 0 AND max_attempts > 0", name="ck_job_attempts"),
        CheckConstraint("source_version >= 1 AND pipeline_version >= 1", name="ck_job_versions"),
        Index("idx_jobs_poll", "status", "available_at"),
        Index("idx_jobs_source", "source_type", "source_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_type: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(Text)
    source_id: Mapped[UUID]
    source_version: Mapped[int] = mapped_column(Integer)
    embedding_model: Mapped[str] = mapped_column(Text)
    pipeline_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(Text, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdminSession(Base):
    __tablename__ = "admin_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AdminSettings(Base):
    __tablename__ = "admin_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_admin_settings_singleton"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_name: Mapped[str] = mapped_column(Text, default="Commerce Lab")
    contact_email: Mapped[str] = mapped_column(Text, default="")
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=5)
    embedding_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ShopperSession(Base):
    __tablename__ = "shopper_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("session_hash", "variant_id", name="uq_cart_session_variant"),
        CheckConstraint("quantity BETWEEN 1 AND 20", name="ck_cart_quantity"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_hash: Mapped[str] = mapped_column(ForeignKey("shopper_sessions.token_hash", ondelete="CASCADE"), index=True)
    variant_id: Mapped[UUID] = mapped_column(ForeignKey("product_variants.id", ondelete="CASCADE"))
    quantity: Mapped[int] = mapped_column(Integer)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("session_hash", "idempotency_key", name="uq_order_idempotency"),
        CheckConstraint("status IN ('pending','confirmed','shipping','completed','cancelled')", name="ck_order_status"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    tenant_id: Mapped[str] = mapped_column(Text)
    session_hash: Mapped[str] = mapped_column(ForeignKey("shopper_sessions.token_hash"), index=True)
    idempotency_key: Mapped[UUID]
    request_hash: Mapped[str] = mapped_column(String(64))
    customer_name: Mapped[str] = mapped_column(Text)
    phone: Mapped[str] = mapped_column(Text)
    address: Mapped[str] = mapped_column(Text)
    note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, default="pending")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 0))
    shipping_fee: Mapped[Decimal] = mapped_column(Numeric(14, 0))
    total: Mapped[Decimal] = mapped_column(Numeric(18, 0))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    variant_id: Mapped[UUID | None] = mapped_column(ForeignKey("product_variants.id", ondelete="SET NULL"))
    product_name: Mapped[str] = mapped_column(Text)
    sku: Mapped[str] = mapped_column(Text)
    options: Mapped[dict[str, Any]] = mapped_column(JSONB)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 0))
    quantity: Mapped[int] = mapped_column(Integer)


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_customer_tenant_email"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(String(254))
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(Text)
    owner_hash: Mapped[str] = mapped_column(ForeignKey("shopper_sessions.token_hash"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CustomerSession(Base):
    __tablename__ = "customer_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class CustomerAuthLimit(Base):
    __tablename__ = "customer_auth_limits"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
