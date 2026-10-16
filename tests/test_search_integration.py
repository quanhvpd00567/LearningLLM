"""Run against a migrated disposable PostgreSQL: TEST_DATABASE_URL=... pytest."""
import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import DocumentChunk
from app.db.session import create_database
from app.schemas.search import MetadataFilter, SearchRequest
from app.services.search import SearchService


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="Requires disposable PostgreSQL with pgvector")
def test_orm_vector_ranking_and_filters():
    async def run():
        engine, _ = create_database(os.environ["TEST_DATABASE_URL"])
        vector = [1.0] + [0.0] * 1023

        class Embedding:
            model = "qwen3-embedding:0.6b"
            async def embed_query(self, query):
                return vector

        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()
                sessions = async_sessionmaker(connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
                async with sessions() as session:
                    for name, tenant, status, category, embedding in [
                        ("match", "shop", "current", "shoes", vector),
                        ("less similar", "shop", "current", "shoes", [0.0, 1.0] + [0.0] * 1022),
                        ("other tenant", "other", "current", "shoes", vector),
                        ("archived", "shop", "archived", "shoes", vector),
                        ("other category", "shop", "current", "bags", vector),
                    ]:
                        session.add(DocumentChunk(
                            document_id=uuid4(), content=name, tenant_id=tenant,
                            status=status, language="vi", embedding=embedding,
                            metadata_json={"category": category},
                            embedding_model=Embedding.model, pipeline_version=1,
                        ))
                    for other_model, pipeline in [("another-model", 1), (None, 1), (Embedding.model, 2)]:
                        session.add(DocumentChunk(
                            document_id=uuid4(), content="incompatible vector", tenant_id="shop",
                            status="current", language="vi", embedding=vector,
                            metadata_json={"category": "shoes"},
                            embedding_model=other_model, pipeline_version=pipeline,
                        ))
                    await session.commit()
                result = await SearchService(sessions, Embedding()).search(SearchRequest(
                    query="giày", filter=MetadataFilter(tenant_id="shop", language="vi", metadata={"category": "shoes"}),
                ))
                assert [row.content for row in result.results] == ["match", "less similar"]
                assert [row.score for row in result.results] == [1.0, 0.5]
                await transaction.rollback()
        finally:
            await engine.dispose()
    asyncio.run(run())
