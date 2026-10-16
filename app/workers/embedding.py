import asyncio
from contextlib import suppress
from dataclasses import dataclass
from hashlib import sha256
import json
import logging

from fastapi import HTTPException
from sqlalchemy import delete, func, or_, select

from app.chatbot.rag.chunking import chunk_text
from app.db.models import Category, DocumentChunk, Job, KnowledgeDocument, Product, ProductVariant
from app.workers.job_queue import Claim, JobQueue

logger = logging.getLogger(__name__)
SOURCE_MODELS = {"product": Product, "knowledge": KnowledgeDocument}


@dataclass(frozen=True)
class Snapshot:
    version: int
    active: bool
    tenant_id: str
    title: str
    content: str
    metadata: dict


class EmbeddingWorker:
    def __init__(self, sessions, embedding, worker_id: str, batch_size: int = 8,
                 lease_seconds: float = 600, retry_seconds: float = 5):
        if batch_size < 1 or lease_seconds <= 0 or retry_seconds < 0:
            raise ValueError("Invalid worker configuration")
        self.sessions = sessions
        self.embedding = embedding
        self.batch_size = batch_size
        self.queue = JobQueue(sessions, embedding.model, worker_id, lease_seconds, retry_seconds)

    async def snapshot(self, claim: Claim) -> Snapshot | None:
        async with self.sessions() as session:
            source = await session.get(SOURCE_MODELS[claim.source_type], claim.source_id)
            if source is None:
                return None
            if claim.source_type == "knowledge":
                return Snapshot(source.source_version, source.is_active, source.tenant_id,
                                source.title, source.content, {"source_type": "knowledge", "source": source.title})
            category = await session.get(Category, source.category_id)
            variants = (await session.scalars(select(ProductVariant).where(
                ProductVariant.product_id == source.id,
            ).order_by(ProductVariant.sku))).all()
            # Exclude price/stock: they must be fetched live by ecommerce services.
            content = "\n\n".join([
                source.description,
                "Thuộc tính: " + json.dumps(source.attributes, ensure_ascii=False, sort_keys=True),
                "Biến thể: " + json.dumps([{"sku": v.sku, **v.options} for v in variants], ensure_ascii=False, sort_keys=True),
            ])
            return Snapshot(source.source_version, source.is_active, source.tenant_id, source.name,
                            content, {"source_type": "product", "product_id": str(source.id),
                                      "source": source.name, "category": category.slug if category else None})

    async def process(self, claim: Claim) -> str:
        snapshot = await self.snapshot(claim)
        texts, vectors = [], []
        valid = snapshot is not None and snapshot.version == claim.source_version
        expected_active = claim.job_type == "embed_source"
        if valid and snapshot.active == expected_active and expected_active:
            texts = [f"{snapshot.title}\n\n{part}" for part in chunk_text(snapshot.content)]
            if not texts:
                raise ValueError("Source has no content")
            for start in range(0, len(texts), self.batch_size):
                vectors.extend(await self.embedding.embed_documents(texts[start:start + self.batch_size]))
        return await self.publish(claim, snapshot, texts, vectors)

    async def publish(self, claim: Claim, snapshot: Snapshot | None, texts, vectors) -> str:
        async with self.sessions.begin() as session:
            # Same source -> job lock order as SourceService, avoiding deadlocks.
            source = await session.scalar(select(SOURCE_MODELS[claim.source_type]).where(
                SOURCE_MODELS[claim.source_type].id == claim.source_id,
            ).with_for_update())
            job = await session.scalar(select(Job).where(
                Job.id == claim.id, Job.status == "processing", Job.locked_by == claim.token,
            ).with_for_update())
            if job is None:
                return "lost_lease"
            valid = (source is not None and snapshot is not None
                     and source.source_version == claim.source_version == snapshot.version
                     and source.is_active == (claim.job_type == "embed_source"))
            if valid:
                await session.execute(delete(DocumentChunk).where(
                    DocumentChunk.document_id == claim.source_id,
                    DocumentChunk.tenant_id == source.tenant_id,
                    or_(DocumentChunk.source_type == claim.source_type, DocumentChunk.source_type.is_(None)),
                ))
                if source.is_active:
                    if not texts:
                        raise ValueError("Missing embeddings for active source")
                    for index, (content, vector) in enumerate(zip(texts, vectors, strict=True)):
                        session.add(DocumentChunk(
                            document_id=source.id, source_type=claim.source_type,
                            source_version=source.source_version, embedding_model=claim.embedding_model,
                            pipeline_version=claim.pipeline_version, chunk_index=index,
                            content_hash=sha256(content.encode()).hexdigest(),
                            content=content, embedding=vector, tenant_id=source.tenant_id,
                            language="vi", status="current", metadata_json=snapshot.metadata,
                        ))
            job.status = "completed" if valid else "superseded"
            job.completed_at = func.clock_timestamp()
            job.last_error = None
            job.locked_at = None
            job.locked_by = None
            # Flush here: a vector write failure also rolls back deletion and job completion.
            await session.flush()
            return job.status

    async def _heartbeat(self, claim):
        while True:
            await asyncio.sleep(min(30, self.queue.lease_seconds / 3))
            try:
                if not await self.queue.heartbeat(claim):
                    return
            except Exception as exc:
                logger.warning("Heartbeat error job=%s type=%s", claim.id, type(exc).__name__)

    async def run_once(self) -> bool:
        await self.queue.recover_stale()
        claim = await self.queue.claim()
        if claim is None:
            return False
        heartbeat = asyncio.create_task(self._heartbeat(claim))
        try:
            result = await self.process(claim)
            logger.info("Job %s %s", claim.id, result)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc.detail}" if isinstance(exc, HTTPException) else type(exc).__name__
            await self.queue.fail(claim, error)
            logger.warning("Job %s will retry or failed: %s", claim.id, error)
        finally:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat
        return True
