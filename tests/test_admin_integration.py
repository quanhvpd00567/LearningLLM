import asyncio
from datetime import timedelta
import os
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routes import admin
from app.core.config import get_settings
from app.db.models import AdminSession, Base, Job, Product
from app.db.session import create_database
from app.workers.job_queue import JobQueue

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="Requires PostgreSQL with pgvector")
PASSWORD = "integration-admin-pass"
MODEL = "qwen3-embedding:0.6b"


@pytest.fixture(autouse=True)
def admin_credentials(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", PASSWORD)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def run_admin(scenario):
    async def run():
        engine, _ = create_database(os.environ["TEST_DATABASE_URL"])
        schema = "admin_test_" + uuid4().hex
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        test_engine = create_async_engine(make_url(os.environ["TEST_DATABASE_URL"]).set(drivername="postgresql+asyncpg"),
                                         connect_args={"server_settings":{"search_path":f"{schema},public"}})
        try:
            async with test_engine.begin() as connection:
                await connection.run_sync(lambda c: Base.metadata.create_all(c, checkfirst=False))
            sessions = async_sessionmaker(test_engine, expire_on_commit=False)
            app = FastAPI()
            app.state.db_sessions = sessions
            app.include_router(admin.auth_router, prefix="/api/v1")
            app.include_router(admin.router, prefix="/api/v1")
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                await scenario(client, sessions)
        finally:
            await test_engine.dispose()
            async with engine.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await engine.dispose()
    asyncio.run(run())


async def login(client):
    response = await client.post("/api/v1/admin/auth/login", json={"username":"admin", "password":PASSWORD})
    assert response.status_code == 200, response.text
    return response


async def category(client):
    response = await client.post("/api/v1/admin/categories", json={"name":"Giày đi bộ", "slug":"walking"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def product(client, category_id, sku="DEMO-42"):
    data = {"category_id":category_id,"name":"Giày Daily", "description":"Giày đi bộ đế êm", "attributes":{},
            "is_active":True, "variants":[{"sku":sku,"options":{"size":42},"price":"500000","stock":12}]}
    response = await client.post("/api/v1/admin/products", json=data)
    assert response.status_code == 201, response.text
    return data, response.json()


def test_auth_cookie_expiry_origin_and_logout():
    async def scenario(client, sessions):
        assert (await client.get("/api/v1/admin/products")).status_code == 401
        assert (await client.post("/api/v1/admin/auth/login", json={"username":"admin","password":"wrong"})).status_code == 401
        response = await login(client)
        cookie = response.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie
        assert (await client.get("/api/v1/admin/auth/me")).json()["username"] == "admin"
        assert (await client.post("/api/v1/admin/categories", json={"name":"Bad", "slug":"bad"}, headers={"Origin":"https://evil.example"})).status_code == 403
        assert (await client.post("/api/v1/admin/auth/logout")).status_code == 200
        assert (await client.get("/api/v1/admin/products")).status_code == 401
        await login(client)
        async with sessions.begin() as session:
            await session.execute(update(AdminSession).values(expires_at=func.clock_timestamp()-timedelta(seconds=1)))
        assert (await client.get("/api/v1/admin/auth/me")).status_code == 401
    run_admin(scenario)


def test_product_crud_version_guard_price_and_removed_variant_jobs():
    async def scenario(client, sessions):
        await login(client)
        category_id = await category(client)
        data, item = await product(client, category_id)
        assert item["source_version"] == 2
        async with sessions() as session:
            count_before = await session.scalar(select(func.count()).select_from(Job))
        data["expected_version"] = item["source_version"]
        data["variants"][0].update(price="600000", stock=0)
        response = await client.put("/api/v1/admin/products/"+item["id"], json=data)
        assert response.status_code == 200, response.text
        assert response.json()["source_version"] == 2
        async with sessions() as session:
            assert await session.scalar(select(func.count()).select_from(Job)) == count_before
        data["name"] = "Giày Daily mới"
        updated = await client.put("/api/v1/admin/products/"+item["id"], json=data)
        assert updated.status_code == 200
        assert updated.json()["source_version"] == 3
        assert (await client.put("/api/v1/admin/products/"+item["id"], json=data)).status_code == 409
        data.update(expected_version=3, variants=[])
        removed = await client.put("/api/v1/admin/products/"+item["id"], json=data)
        assert removed.status_code == 200 and removed.json()["variants"] == []
        listing = await client.get("/api/v1/admin/products?q=Daily&page=1")
        assert listing.json()["total"] == 1
        assert (await client.get("/api/v1/admin/overview")).status_code == 200
        # Duplicate SKU belongs to another product; source+job must roll back.
        await product(client, category_id, "UNIQUE-42")
        conflict = await client.post("/api/v1/admin/products", json={**data,"variants":[{"sku":"UNIQUE-42","options":{},"price":"1","stock":1}]})
        assert conflict.status_code == 422
        async with sessions() as session:
            assert await session.scalar(select(func.count()).select_from(Product)) == 2
    run_admin(scenario)


def test_settings_pause_claim_and_reject_embedding_model_change():
    async def scenario(client, sessions):
        await login(client)
        await product(client, await category(client))
        initial = await client.get("/api/v1/admin/settings")
        assert initial.json()["runtime"]["embedding_model"] == MODEL
        body = {"shop_name":"Test Store", "contact_email":"test@example.com", "low_stock_threshold":15, "embedding_paused":True}
        assert (await client.put("/api/v1/admin/settings", json=body)).status_code == 200
        queue = JobQueue(sessions, MODEL, "admin-test")
        assert await queue.claim() is None
        overview = (await client.get("/api/v1/admin/overview")).json()
        assert overview["low_stock"] == 1 and overview["shop_name"] == "Test Store"
        body["embedding_paused"] = False
        assert (await client.put("/api/v1/admin/settings", json=body)).status_code == 200
        assert await queue.claim() is not None
        assert (await client.put("/api/v1/admin/settings", json={**body,"embedding_model":"other"})).status_code == 422
    run_admin(scenario)


def test_knowledge_retry_and_category_update_generate_jobs():
    async def scenario(client, sessions):
        await login(client)
        category_id = await category(client)
        _, item = await product(client, category_id)
        assert (await client.put("/api/v1/admin/categories/"+category_id, json={"name":"Đi bộ", "slug":"walk"})).status_code == 200
        changed = (await client.get("/api/v1/admin/products/"+item["id"])).json()
        assert changed["source_version"] == 3 and changed["category"] == "Đi bộ"
        doc = await client.post("/api/v1/admin/knowledge", json={"title":"FAQ", "content":"Đổi trả bảy ngày"})
        assert doc.status_code == 201
        doc_id = doc.json()["id"]
        jobs = (await client.get("/api/v1/admin/jobs?status=pending")).json()
        assert jobs["total"] == 2
        doc_job = next(j for j in jobs["items"] if j["source_type"] == "knowledge")
        assert (await client.post(f'/api/v1/admin/jobs/{doc_job["id"]}/retry')).status_code == 409
        async with sessions.begin() as session:
            await session.execute(update(Job).where(Job.id == doc_job["id"]).values(status="failed", attempts=3))
        assert (await client.post(f'/api/v1/admin/jobs/{doc_job["id"]}/retry')).status_code == 200
        changed_doc = await client.put("/api/v1/admin/knowledge/"+doc_id, json={"title":"FAQ", "content":"Mười ngày", "expected_version":1})
        assert changed_doc.status_code == 200
        assert (await client.put("/api/v1/admin/knowledge/"+doc_id, json={"title":"FAQ", "content":"Stale", "expected_version":1})).status_code == 409
        requeued = await client.post("/api/v1/admin/jobs/reindex")
        assert requeued.status_code == 200 and requeued.json()["requeued"] == 2
    run_admin(scenario)
