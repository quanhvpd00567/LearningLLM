"""Idempotent demo seed. Run: python -m scripts.seed_ecommerce.

Only run on a demo database: repeating restores sample values for these IDs.
No model calls; the seed creates jobs for the next worker stage.
"""
import asyncio
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.db.models import Category, Job, KnowledgeDocument, Product, ProductVariant
from app.db.session import create_database
from app.schemas.sources import KnowledgeInput, ProductInput, VariantInput
from app.services.sources import SourceService


def source_id(key):
    return uuid5(NAMESPACE_URL, f"learningllm:ecommerce-demo:{key}")


async def seed(sessions, embedding_model):
    data = json.loads((Path(__file__).resolve().parents[1] / "data/seed/ecommerce.json").read_text())
    async with sessions.begin() as session:
        for category in data["categories"]:
            await session.execute(insert(Category).values(
                id=source_id(category["slug"]), **category,
            ).on_conflict_do_nothing(index_elements=[Category.slug]))
        categories = dict((await session.execute(select(Category.slug, Category.id))).all())
        service = SourceService(session, embedding_model)
        for product in data["products"]:
            product_id = source_id(product["key"])
            await service.save_product(product_id, ProductInput(
                category_id=categories[product["category"]], name=product["name"],
                description=product["description"], attributes=product["attributes"],
            ))
            for variant in product["variants"]:
                await service.save_variant(product_id, VariantInput(**variant))
        for document in data["knowledge"]:
            await service.save_knowledge(source_id(document["key"]), KnowledgeInput(
                title=document["title"], content=document["content"],
            ))
    async with sessions() as session:
        return {model.__tablename__: await session.scalar(select(func.count()).select_from(model))
                for model in [Product, ProductVariant, KnowledgeDocument, Job]}


async def main():
    settings = get_settings()
    engine, sessions = create_database(settings.database_url)
    try:
        print(await seed(sessions, settings.embedding_model))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
