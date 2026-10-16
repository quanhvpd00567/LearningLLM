"""All source writes and their jobs share the caller's transaction.

Services flush but never commit: callers use `async with session.begin()`.
Lock the source row before changing its content or variants to serialize versions.
"""
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.chatbot.rag.chunking import PIPELINE_VERSION
from app.db.models import Category, DocumentChunk, Job, KnowledgeDocument, Product, ProductVariant
from app.schemas.sources import KnowledgeInput, ProductInput, VariantInput


class SourceService:
    def __init__(self, session: AsyncSession, embedding_model: str, tenant_id: str = "demo"):
        self.session = session
        self.embedding_model = embedding_model
        self.tenant_id = tenant_id

    async def _enqueue(self, source_type: str, source):
        job_type = "embed_source" if source.is_active else "delete_source_embeddings"
        await self.session.execute(insert(Job).values(
            job_type=job_type, source_type=source_type, source_id=source.id,
            source_version=source.source_version, embedding_model=self.embedding_model,
            pipeline_version=PIPELINE_VERSION,
        ).on_conflict_do_nothing(constraint="uq_job_source_profile"))
        await self.session.execute(update(Job).where(
            Job.source_type == source_type, Job.source_id == source.id,
            Job.source_version < source.source_version, Job.status == "pending",
        ).values(status="superseded", completed_at=func.now()))
        # Hide stale content immediately, even before a worker processes the job.
        await self.session.execute(update(DocumentChunk).where(
            DocumentChunk.document_id == source.id,
            DocumentChunk.tenant_id == self.tenant_id,
            or_(DocumentChunk.source_type == source_type, DocumentChunk.source_type.is_(None)),
            DocumentChunk.status == "current",
        ).values(status="archived" if source.is_active else "deleted"))

    async def _locked(self, model, source_id: UUID):
        return await self.session.scalar(select(model).where(
            model.id == source_id, model.tenant_id == self.tenant_id,
        ).with_for_update().execution_options(populate_existing=True))

    async def save_product(self, source_id: UUID, data: ProductInput) -> Product:
        if await self.session.get(Category, data.category_id) is None:
            raise ValueError("Category not found")
        product = await self._locked(Product, source_id)
        values = data.model_dump()
        if product is None:
            product = Product(id=source_id, tenant_id=self.tenant_id, source_version=1, **values)
            self.session.add(product)
        elif all(getattr(product, key) == value for key, value in values.items()):
            return product
        else:
            for key, value in values.items():
                setattr(product, key, value)
            product.source_version += 1
        await self.session.flush()
        await self._enqueue("product", product)
        return product

    async def save_knowledge(self, source_id: UUID, data: KnowledgeInput) -> KnowledgeDocument:
        document = await self._locked(KnowledgeDocument, source_id)
        values = data.model_dump()
        if document is None:
            document = KnowledgeDocument(id=source_id, tenant_id=self.tenant_id, source_version=1, **values)
            self.session.add(document)
        elif all(getattr(document, key) == value for key, value in values.items()):
            return document
        else:
            for key, value in values.items():
                setattr(document, key, value)
            document.source_version += 1
        await self.session.flush()
        await self._enqueue("knowledge", document)
        return document

    async def save_variant(self, product_id: UUID, data: VariantInput) -> ProductVariant:
        product = await self._locked(Product, product_id)
        if product is None:
            raise ValueError("Product not found")
        variant = await self.session.scalar(select(ProductVariant).where(ProductVariant.sku == data.sku))
        changed_content = variant is None or variant.options != data.options
        if variant is None:
            variant = ProductVariant(product_id=product_id, **data.model_dump())
            self.session.add(variant)
        else:
            if variant.product_id != product_id:
                raise ValueError("SKU belongs to another product")
            variant.options = data.options
            variant.price = data.price
            variant.stock = data.stock
        if changed_content:
            product.source_version += 1
        await self.session.flush()
        if changed_content:
            await self._enqueue("product", product)
        return variant
