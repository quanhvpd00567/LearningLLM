"""Use a private schema per test, allowing real commits and concurrent sessions."""
import asyncio
from datetime import timedelta
import os
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.engine import make_url

from app.db.models import Base, Category, DocumentChunk, Job, Product
from app.db.session import create_database
from app.schemas.sources import KnowledgeInput, ProductInput, VariantInput
from app.services.sources import SourceService
from app.workers.embedding import EmbeddingWorker
from scripts.reindex import reindex

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="Requires PostgreSQL with pgvector")
MODEL = "qwen3-embedding:0.6b"


class FakeEmbedding:
    model = MODEL

    def __init__(self):
        self.calls = []
        self.callback = None
        self.failure = None
        self.bad_vector = False

    async def embed_documents(self, texts):
        self.calls.append(texts)
        if self.callback:
            callback, self.callback = self.callback, None
            await callback()
        if self.failure:
            raise self.failure
        return [[1.0] if self.bad_vector else [1.0] + [0.0] * 1023 for _ in texts]


def run_scenario(scenario):
    async def run():
        admin_engine, _ = create_database(os.environ["TEST_DATABASE_URL"])
        schema = "worker_test_" + uuid4().hex
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(make_url(os.environ["TEST_DATABASE_URL"]).set(drivername="postgresql+asyncpg"),
                                     connect_args={"server_settings": {"search_path": f"{schema},public"}})
        try:
            async with engine.begin() as connection:
                # checkfirst=False prevents accidentally reusing public tables.
                await connection.run_sync(lambda c: Base.metadata.create_all(c, checkfirst=False))
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            await scenario(sessions)
        finally:
            await engine.dispose()
            async with admin_engine.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin_engine.dispose()
    asyncio.run(run())


async def create_document(sessions, content="Đổi trả trong bảy ngày."):
    source_id = uuid4()
    async with sessions.begin() as session:
        await SourceService(session, MODEL).save_knowledge(source_id, KnowledgeInput(title="Đổi trả", content=content))
    return source_id


async def get_jobs(sessions):
    async with sessions() as session:
        return (await session.scalars(select(Job).order_by(Job.source_version))).all()


async def get_chunks(sessions):
    async with sessions() as session:
        return (await session.scalars(select(DocumentChunk).order_by(DocumentChunk.chunk_index))).all()


def test_publish_and_reindex_without_duplicate_chunks():
    async def scenario(sessions):
        source_id = await create_document(sessions, "Chính sách đổi trả. " * 200)
        embedding = FakeEmbedding()
        worker = EmbeddingWorker(sessions, embedding, "worker-a", batch_size=2)
        assert await worker.run_once()
        chunks = await get_chunks(sessions)
        assert len(chunks) > 1
        assert all(c.document_id == source_id and c.source_version == 1 and c.content_hash and c.embedding_model == MODEL for c in chunks)
        assert len(embedding.calls) > 1
        assert (await get_jobs(sessions))[0].status == "completed"
        assert not await worker.run_once()
        assert await reindex(sessions, MODEL) == 1
        assert await worker.run_once()
        assert len(await get_chunks(sessions)) == len(chunks)
    run_scenario(scenario)


def test_two_workers_claim_different_jobs():
    async def scenario(sessions):
        await create_document(sessions)
        await create_document(sessions)
        a = EmbeddingWorker(sessions, FakeEmbedding(), "a")
        b = EmbeddingWorker(sessions, FakeEmbedding(), "b")
        first, second = await asyncio.gather(a.queue.claim(), b.queue.claim())
        assert first.id != second.id
        assert first.token != second.token
        assert all(j.status == "processing" and j.attempts == 1 for j in await get_jobs(sessions))
    run_scenario(scenario)


def test_locked_job_is_skipped_without_waiting():
    async def scenario(sessions):
        await create_document(sessions)
        await create_document(sessions)
        worker = EmbeddingWorker(sessions, FakeEmbedding(), "a")
        async with sessions.begin() as session:
            locked = await session.scalar(select(Job).order_by(Job.created_at).with_for_update().limit(1))
            claim = await asyncio.wait_for(worker.queue.claim(), timeout=3)
            assert claim.id != locked.id
    run_scenario(scenario)


def test_expired_claim_cannot_publish_or_fail_new_claim():
    async def scenario(sessions):
        await create_document(sessions)
        a = EmbeddingWorker(sessions, FakeEmbedding(), "a")
        b = EmbeddingWorker(sessions, FakeEmbedding(), "b")
        old = await a.queue.claim()
        async with sessions.begin() as session:
            await session.execute(update(Job).values(locked_at=func.clock_timestamp() - timedelta(seconds=1000)))
        assert await b.queue.recover_stale() == 1
        new = await b.queue.claim()
        assert new.id == old.id and new.token != old.token
        assert await a.process(old) == "lost_lease"
        await a.queue.fail(old, "obsolete failure")
        assert (await get_jobs(sessions))[0].locked_by == new.token
        assert await b.process(new) == "completed"
        assert len(await get_chunks(sessions)) == 1
    run_scenario(scenario)


def test_heartbeat_keeps_claim_alive_and_expired_final_attempt_fails():
    async def scenario(sessions):
        await create_document(sessions)
        worker = EmbeddingWorker(sessions, FakeEmbedding(), "a")
        claim = await worker.queue.claim()
        async with sessions.begin() as session:
            await session.execute(update(Job).values(locked_at=func.clock_timestamp() - timedelta(seconds=1000)))
        assert await worker.queue.heartbeat(claim)
        assert await worker.queue.recover_stale() == 0
        async with sessions.begin() as session:
            await session.execute(update(Job).values(attempts=3, locked_at=func.clock_timestamp() - timedelta(seconds=1000)))
        assert await worker.queue.recover_stale() == 1
        assert (await get_jobs(sessions))[0].status == "failed"
    run_scenario(scenario)


def test_source_updated_during_embedding_discards_old_results():
    async def scenario(sessions):
        source_id = await create_document(sessions)
        embedding = FakeEmbedding()
        async def change_source():
            async with sessions.begin() as session:
                await SourceService(session, MODEL).save_knowledge(source_id, KnowledgeInput(title="Đổi trả", content="Chính sách mới: mười ngày."))
        embedding.callback = change_source
        worker = EmbeddingWorker(sessions, embedding, "a")
        assert await worker.run_once()
        assert not await get_chunks(sessions)
        assert [j.status for j in await get_jobs(sessions)] == ["superseded", "pending"]
        assert await worker.run_once()
        assert all(c.source_version == 2 and "mười ngày" in c.content for c in await get_chunks(sessions))
    run_scenario(scenario)


def test_delete_and_reactivate_source():
    async def scenario(sessions):
        source_id = await create_document(sessions)
        embedding = FakeEmbedding()
        worker = EmbeddingWorker(sessions, embedding, "a")
        await worker.run_once()
        initial_calls = len(embedding.calls)
        async with sessions.begin() as session:
            await SourceService(session, MODEL).save_knowledge(source_id, KnowledgeInput(title="Đổi trả", content="Đổi trong bảy ngày", is_active=False))
        await worker.run_once()
        assert not await get_chunks(sessions)
        assert len(embedding.calls) == initial_calls
        async with sessions.begin() as session:
            await SourceService(session, MODEL).save_knowledge(source_id, KnowledgeInput(title="Đổi trả", content="Đổi trong bảy ngày", is_active=True))
        await worker.run_once()
        assert len(await get_chunks(sessions)) == 1
    run_scenario(scenario)


def test_retry_delay_and_max_attempts():
    async def scenario(sessions):
        await create_document(sessions)
        embedding = FakeEmbedding()
        embedding.failure = HTTPException(503, "Ollama unavailable")
        worker = EmbeddingWorker(sessions, embedding, "a", retry_seconds=60)
        async with sessions.begin() as session:
            await session.execute(update(Job).values(max_attempts=2))
        await worker.run_once()
        job = (await get_jobs(sessions))[0]
        assert job.status == "pending" and job.attempts == 1 and "HTTPException" in job.last_error
        assert await worker.queue.claim() is None
        async with sessions.begin() as session:
            await session.execute(update(Job).values(available_at=func.clock_timestamp() - timedelta(seconds=1)))
        await worker.run_once()
        job = (await get_jobs(sessions))[0]
        assert job.status == "failed" and job.attempts == 2 and job.completed_at is not None
        assert not await worker.run_once()
    run_scenario(scenario)


def test_failed_vector_insert_rolls_back_replacement_and_completion():
    async def scenario(sessions):
        await create_document(sessions)
        embedding = FakeEmbedding()
        worker = EmbeddingWorker(sessions, embedding, "a")
        await worker.run_once()
        previous = await get_chunks(sessions)
        await reindex(sessions, MODEL)
        embedding.bad_vector = True
        await worker.run_once()
        chunks = await get_chunks(sessions)
        assert [c.id for c in chunks] == [c.id for c in previous]
        assert (await get_jobs(sessions))[0].status == "pending"
    run_scenario(scenario)


def test_product_embedding_excludes_live_commerce_fields():
    async def scenario(sessions):
        async with sessions.begin() as session:
            category = Category(id=uuid4(), name="Giày", slug="walking")
            session.add(category)
            await session.flush()
            service = SourceService(session, MODEL)
            product = await service.save_product(uuid4(), ProductInput(category_id=category.id, name="Giày đi bộ", description="Đế êm"))
            await service.save_variant(product.id, VariantInput(sku="DEMO-42", options={"size":42}, price=765432, stock=9876))
        embedding = FakeEmbedding()
        worker = EmbeddingWorker(sessions, embedding, "a")
        await worker.run_once()
        content = " ".join(t for batch in embedding.calls for t in batch)
        assert "DEMO-42" in content and "42" in content
        assert "765432" not in content and "9876" not in content
        assert (await get_chunks(sessions))[0].metadata_json["category"] == "walking"
    run_scenario(scenario)


def test_worker_ignores_incompatible_model_and_reindex_skips_processing():
    async def scenario(sessions):
        await create_document(sessions)
        worker = EmbeddingWorker(sessions, FakeEmbedding(), "a")
        claim = await worker.queue.claim()
        assert await reindex(sessions, MODEL) == 0
        await worker.process(claim)
        assert await reindex(sessions, "another-model") == 1
        assert not await worker.run_once()
    run_scenario(scenario)
