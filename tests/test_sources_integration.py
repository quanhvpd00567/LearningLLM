"""Transaction and versioning tests against a migrated disposable PostgreSQL."""
import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Category, DocumentChunk, Job, KnowledgeDocument, Product
from app.db.session import create_database
from app.schemas.sources import KnowledgeInput, ProductInput, VariantInput
from app.services.sources import SourceService

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="Requires PostgreSQL with pgvector")
MODEL = "qwen3-embedding:0.6b"


def run_transaction(scenario):
    async def run():
        engine, _ = create_database(os.environ["TEST_DATABASE_URL"])
        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()
                sessions = async_sessionmaker(connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
                await scenario(sessions)
                await transaction.rollback()
        finally:
            await engine.dispose()
    asyncio.run(run())


async def count_jobs(session, source_id):
    return await session.scalar(select(func.count()).select_from(Job).where(Job.source_id == source_id))


def test_create_noop_update_and_stale_chunks_are_hidden():
    async def scenario(sessions):
        source_id = uuid4()
        async with sessions.begin() as session:
            service = SourceService(session, MODEL)
            data = KnowledgeInput(title="Đổi trả", content="Đổi trong 7 ngày")
            document = await service.save_knowledge(source_id, data)
            assert document.source_version == 1
            await service.save_knowledge(source_id, data)
            await service._enqueue("knowledge", document)
            assert await count_jobs(session, source_id) == 1
            session.add(DocumentChunk(document_id=source_id, source_type="knowledge", tenant_id="demo", content="old"))
            await session.flush()
            document = await service.save_knowledge(source_id, data.model_copy(update={"content": "Đổi trong 10 ngày"}))
            assert document.source_version == 2
            assert await count_jobs(session, source_id) == 2
            statuses = (await session.scalars(select(Job.status).where(Job.source_id == source_id).order_by(Job.source_version))).all()
            assert statuses == ["superseded", "pending"]
            assert await session.scalar(select(DocumentChunk.status).where(DocumentChunk.document_id == source_id)) == "archived"
    run_transaction(scenario)


def test_source_and_job_rollback_together():
    async def scenario(sessions):
        source_id = uuid4()
        with pytest.raises(RuntimeError):
            async with sessions.begin() as session:
                await SourceService(session, MODEL).save_knowledge(source_id, KnowledgeInput(title="FAQ", content="Answer"))
                raise RuntimeError("simulated failure after enqueue")
        async with sessions() as session:
            assert await session.get(KnowledgeDocument, source_id) is None
            assert await count_jobs(session, source_id) == 0
    run_transaction(scenario)


def test_price_stock_change_does_not_enqueue_but_options_do():
    async def scenario(sessions):
        async with sessions.begin() as session:
            category = Category(id=uuid4(), name="Giày", slug=str(uuid4()))
            session.add(category)
            await session.flush()
            service = SourceService(session, MODEL)
            product = await service.save_product(uuid4(), ProductInput(category_id=category.id, name="Giày đi bộ", description="Đế êm"))
            variant = VariantInput(sku=str(uuid4()), options={"size": 42}, price=500000, stock=10)
            await service.save_variant(product.id, variant)
            version = product.source_version
            job_count = await count_jobs(session, product.id)
            await service.save_variant(product.id, variant.model_copy(update={"price": 600000, "stock": 0}))
            assert product.source_version == version
            assert await count_jobs(session, product.id) == job_count
            await service.save_variant(product.id, variant.model_copy(update={"options": {"size": 43}}))
            assert product.source_version == version + 1
            assert await count_jobs(session, product.id) == job_count + 1
    run_transaction(scenario)


def test_deactivation_queues_delete_and_hides_chunks():
    async def scenario(sessions):
        async with sessions.begin() as session:
            service = SourceService(session, MODEL)
            source_id = uuid4()
            data = KnowledgeInput(title="FAQ", content="Trả lời")
            await service.save_knowledge(source_id, data)
            session.add(DocumentChunk(document_id=source_id, source_type="knowledge", tenant_id="demo", content="old"))
            await session.flush()
            await service.save_knowledge(source_id, data.model_copy(update={"is_active": False}))
            job = await session.scalar(select(Job).where(Job.source_id == source_id, Job.source_version == 2))
            assert job.job_type == "delete_source_embeddings"
            assert await session.scalar(select(DocumentChunk.status).where(DocumentChunk.document_id == source_id)) == "deleted"
    run_transaction(scenario)


def test_concurrent_updates_serialize_versions():
    async def run():
        engine, sessions = create_database(os.environ["TEST_DATABASE_URL"])
        source_id = uuid4()
        try:
            async with sessions.begin() as session:
                await SourceService(session, MODEL).save_knowledge(source_id, KnowledgeInput(title="FAQ", content="original"))

            async def edit(content):
                async with sessions.begin() as session:
                    await SourceService(session, MODEL).save_knowledge(source_id, KnowledgeInput(title="FAQ", content=content))

            await asyncio.gather(edit("edit A"), edit("edit B"))
            async with sessions() as session:
                document = await session.get(KnowledgeDocument, source_id)
                assert document.source_version == 3
                versions = (await session.scalars(select(Job.source_version).where(Job.source_id == source_id).order_by(Job.source_version))).all()
                assert versions == [1, 2, 3]
        finally:
            from sqlalchemy import delete
            async with sessions.begin() as session:
                await session.execute(delete(Job).where(Job.source_id == source_id))
                await session.execute(delete(KnowledgeDocument).where(KnowledgeDocument.id == source_id))
            await engine.dispose()
    asyncio.run(run())
