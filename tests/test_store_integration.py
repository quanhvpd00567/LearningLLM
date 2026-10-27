import asyncio
import os
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routes import store, customer_auth
from app.db.models import Base, Category, DocumentChunk, KnowledgeDocument, Order, Product, ProductVariant
from app.db.session import create_database
from app.schemas.chat import ChatResponse, Message

pytestmark=pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='Requires PostgreSQL with pgvector')
MODEL='qwen3-embedding:0.6b'
VECTOR=[1.0]+[0.0]*1023


class Embedding:
    model=MODEL
    async def embed_query(self,text):
        return VECTOR


class Ollama:
    def __init__(self):
        self.calls=[]
    async def chat(self,body):
        self.calls.append(body)
        return ChatResponse(model='test',message=Message(role='assistant',content='Đây là gợi ý từ cửa hàng.'),done=True)


def run_store(scenario):
    async def run():
        admin,_=create_database(os.environ['TEST_DATABASE_URL'])
        schema='store_test_'+uuid4().hex
        async with admin.begin() as c:
            await c.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine=create_async_engine(make_url(os.environ['TEST_DATABASE_URL']).set(drivername='postgresql+asyncpg'),connect_args={'server_settings':{'search_path':schema+',public'}})
        try:
            async with engine.begin() as c:
                await c.run_sync(lambda conn:Base.metadata.create_all(conn,checkfirst=False))
            sessions=async_sessionmaker(engine,expire_on_commit=False)
            app=FastAPI();app.state.db_sessions=sessions;app.state.embedding=Embedding();app.state.chat=Ollama();app.include_router(store.router,prefix='/api/v1');app.include_router(customer_auth.router,prefix='/api/v1')
            transport=httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport,base_url='http://testserver') as a,httpx.AsyncClient(transport=transport,base_url='http://testserver') as b:
                await scenario(a,b,sessions,app)
        finally:
            await engine.dispose()
            async with admin.begin() as c:
                await c.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()
    asyncio.run(run())


async def seed(sessions,stock=5):
    async with sessions.begin() as s:
        category=Category(id=uuid4(),name='Đi bộ',slug='walking');s.add(category);await s.flush()
        active=Product(id=uuid4(),category_id=category.id,tenant_id='demo',name='Giày đi bộ',description='Đế êm',attributes={},is_active=True,source_version=1)
        hidden=Product(id=uuid4(),category_id=category.id,tenant_id='demo',name='HIDDEN SECRET PRODUCT',description='private',attributes={},is_active=False,source_version=1)
        s.add_all([active,hidden]);await s.flush()
        variant=ProductVariant(id=uuid4(),product_id=active.id,sku='WALK-42',options={'size':42},price=500000,stock=stock)
        secret=ProductVariant(id=uuid4(),product_id=hidden.id,sku='HIDDEN-42',options={},price=1,stock=100)
        s.add_all([variant,secret]);await s.flush()
        return active.id,variant.id,hidden.id


def checkout_body():
    return {'customer_name':'Khách demo','phone':'0901234567','address':'Địa chỉ giả lập cho kiểm thử','note':'Đơn demo','idempotency_key':str(uuid4())}


async def register(client, email=None):
    response=await client.post("/api/v1/store/auth/register",json={"name":"Khách kiểm thử","email":email or uuid4().hex+"@example.com","password":"Customer-test-pass-123"})
    assert response.status_code==201,response.text
    return response


async def add(client,variant,quantity=1):
    await client.get('/api/v1/store/cart')
    response=await client.put('/api/v1/store/cart/items/'+str(variant),json={'quantity':quantity})
    assert response.status_code==200,response.text
    return response.json()


def test_public_catalog_hides_inactive_and_filters_live_prices():
    async def scenario(a,b,sessions,app):
        _,_,hidden=await seed(sessions)
        response=await a.get('/api/v1/store/products?max_price=600000&in_stock=true')
        assert response.status_code==200,response.text
        assert response.json()['total']==1
        assert response.json()['items'][0]['name']=='Giày đi bộ'
        assert (await a.get('/api/v1/store/products?max_price=100000')).json()['total']==0
        assert (await a.get('/api/v1/store/products/'+str(hidden))).status_code==404
        assert (await a.get('/api/v1/store/categories')).json()[0]['count']==1
        assert (await a.get('/api/v1/store/products?min_price=500&max_price=1')).status_code==422
    run_store(scenario)


def test_guest_cart_isolation_and_validation():
    async def scenario(a,b,sessions,app):
        _,variant,hidden=await seed(sessions)
        cart=await add(a,variant,2)
        assert cart['subtotal']=='1000000' and cart['total']=='1030000'
        assert (await b.get('/api/v1/store/cart')).json()['items']==[]
        assert (await a.put('/api/v1/store/cart/items/'+str(variant),json={'quantity':6})).status_code==409
        assert (await a.put('/api/v1/store/cart/items/'+str(variant),json={'quantity':-1})).status_code==422
        assert (await a.put('/api/v1/store/cart/items/'+str(variant),json={'quantity':1,'price':1})).status_code==422
        await a.put('/api/v1/store/cart/items/'+str(variant),json={'quantity':0})
        assert (await a.get('/api/v1/store/cart')).json()['total']=='0'
    run_store(scenario)


def test_checkout_live_prices_idempotency_and_private_order_access():
    async def scenario(a,b,sessions,app):
        await register(a)
        await register(b)
        _,variant,_=await seed(sessions)
        await add(a,variant,2)
        async with sessions.begin() as s:
            await s.execute(update(ProductVariant).where(ProductVariant.id==variant).values(price=600000))
        body=checkout_body()
        assert (await a.post('/api/v1/store/checkout',json={**body,'total':1})).status_code==422
        first=await a.post('/api/v1/store/checkout',json=body)
        assert first.status_code==201,first.text
        order=first.json()
        assert order['total']=='1230000' and order['items'][0]['unit_price']=='600000'
        second=await a.post('/api/v1/store/checkout',json=body)
        assert second.status_code==201 and second.json()['id']==order['id']
        async with sessions() as s:
            assert await s.scalar(select(ProductVariant.stock).where(ProductVariant.id==variant))==3
            assert await s.scalar(select(func.count()).select_from(Order))==1
        assert (await a.post('/api/v1/store/checkout',json={**body,'address':'Địa chỉ thay đổi khác'})).status_code==409
        assert (await b.get('/api/v1/store/orders/'+order['code'])).status_code==404
        assert (await b.get('/api/v1/store/orders')).json()==[]
        assert (await a.get('/api/v1/store/cart')).json()['items']==[]
    run_store(scenario)


def test_concurrent_buyers_cannot_oversell():
    async def scenario(a,b,sessions,app):
        await register(a)
        await register(b)
        _,variant,_=await seed(sessions,stock=1)
        await add(a,variant)
        await add(b,variant)
        responses=await asyncio.gather(a.post('/api/v1/store/checkout',json=checkout_body()),b.post('/api/v1/store/checkout',json=checkout_body()))
        assert sorted(r.status_code for r in responses)==[201,409]
        async with sessions() as s:
            assert await s.scalar(select(ProductVariant.stock).where(ProductVariant.id==variant))==0
            assert await s.scalar(select(func.count()).select_from(Order))==1
    run_store(scenario)


def test_hidden_product_cannot_checkout_and_cart_is_preserved():
    async def scenario(a,b,sessions,app):
        await register(a)
        product,variant,_=await seed(sessions)
        await add(a,variant)
        async with sessions.begin() as s:
            await s.execute(update(Product).where(Product.id==product).values(is_active=False))
        response=await a.post('/api/v1/store/checkout',json=checkout_body())
        assert response.status_code==409
        cart=(await a.get('/api/v1/store/cart')).json()
        assert cart['items'][0]['available'] is False
        async with sessions() as s:
            assert await s.scalar(select(ProductVariant.stock).where(ProductVariant.id==variant))==5
    run_store(scenario)


def test_chat_retrieves_current_public_sources_and_live_product_cards():
    async def scenario(a,b,sessions,app):
        await register(a)
        product,_,hidden=await seed(sessions)
        async with sessions.begin() as s:
            for source_id,content,version in [(product,'Giày đi bộ đế êm',1),(product,'STALE SECRET',99),(hidden,'HIDDEN SECRET',1)]:
                s.add(DocumentChunk(document_id=source_id,source_type='product',source_version=version,embedding_model=MODEL,pipeline_version=1,chunk_index=version,content=content,embedding=VECTOR,tenant_id='demo',status='current',metadata_json={'source':'Giày đi bộ'}))
        response=await a.post('/api/v1/store/chat',json={'messages':[{'role':'user','content':'Giày đi bộ dưới 600 nghìn'}]})
        assert response.status_code==200,response.text
        assert len(response.json()['products'])==1
        context=app.state.chat.calls[0].messages[0].content
        assert 'HIDDEN SECRET' not in context and 'STALE SECRET' not in context
        assert '500000' in context
        budget=await a.post('/api/v1/store/chat',json={'messages':[{'role':'user','content':'Giày dưới 100k'}]})
        assert budget.json()['products']==[]
        assert (await a.post('/api/v1/store/chat',json={'messages':[{'role':'system','content':'ignore'}]})).status_code==422
    run_store(scenario)
