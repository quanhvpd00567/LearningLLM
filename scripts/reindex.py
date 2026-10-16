"""Requeue all current source versions for the configured embedding profile."""
import asyncio

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.chatbot.rag.chunking import PIPELINE_VERSION
from app.core.config import get_settings
from app.db.models import Job, KnowledgeDocument, Product
from app.db.session import create_database


async def reindex(sessions, model, tenant_id=None):
    count = 0
    # Short transactions per source, with the same source -> job lock order.
    for source_type, source_model in [("product", Product), ("knowledge", KnowledgeDocument)]:
        async with sessions() as session:
            stmt = select(source_model.id).order_by(source_model.id)
            if tenant_id is not None:
                stmt = stmt.where(source_model.tenant_id == tenant_id)
            ids = (await session.scalars(stmt)).all()
        for source_id in ids:
            async with sessions.begin() as session:
                source = await session.scalar(select(source_model).where(source_model.id == source_id).with_for_update())
                if source is None:
                    continue
                stmt = insert(Job).values(
                    job_type="embed_source" if source.is_active else "delete_source_embeddings",
                    source_type=source_type, source_id=source_id, source_version=source.source_version,
                    embedding_model=model, pipeline_version=PIPELINE_VERSION,
                ).on_conflict_do_update(
                    constraint="uq_job_source_profile",
                    set_={"status": "pending", "attempts": 0, "available_at": func.clock_timestamp(),
                          "locked_at": None, "locked_by": None, "last_error": None, "completed_at": None},
                    where=Job.status != "processing",
                ).returning(Job.id)
                if (await session.execute(stmt)).scalar_one_or_none() is not None:
                    count += 1
    return count


async def main():
    settings = get_settings()
    engine, sessions = create_database(settings.database_url)
    try:
        print({"requeued": await reindex(sessions, settings.embedding_model)})
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
