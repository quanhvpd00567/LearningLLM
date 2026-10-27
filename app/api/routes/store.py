from datetime import timedelta
from hashlib import sha256
import secrets
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, or_, select

from app.core.admin_auth import same_origin
from app.core.customer_auth import store_db, optional_customer, require_customer, customer_owner
from app.core.config import get_settings
from app.db.models import AdminSettings, CartItem, Category, KnowledgeDocument, Order, Product, ProductVariant, ShopperSession
from app.schemas.store import CartUpdate, CheckoutInput, StoreChatInput
from app.services.store import card, cart_view, checkout, order_view

router = APIRouter(prefix="/store", tags=["Storefront"])
COOKIE = "commerce_shopper"


def tenant():
    return get_settings().admin_tenant_id


async def shopper(request:Request,response:Response,user=Depends(optional_customer,scope="function"),session=Depends(store_db,scope="function")):
    if user is not None:
        await session.scalar(select(ShopperSession).where(ShopperSession.token_hash==user.owner_hash).with_for_update())
        return user.owner_hash
    token = request.cookies.get(COOKIE,"")
    token_hash = sha256(token.encode()).hexdigest()
    stmt = select(ShopperSession).where(ShopperSession.token_hash==token_hash,ShopperSession.expires_at>func.clock_timestamp())
    if request.method != "GET":
        stmt = stmt.with_for_update()
    owner = await session.scalar(stmt) if token else None
    if owner is None:
        token = secrets.token_urlsafe(48)
        token_hash = sha256(token.encode()).hexdigest()
        now = await session.scalar(select(func.clock_timestamp()))
        owner = ShopperSession(token_hash=token_hash,expires_at=now+timedelta(days=30))
        session.add(owner)
        await session.flush()
        response.set_cookie(COOKIE,token,max_age=30*86400,httponly=True,samesite="strict",
                            secure=get_settings().store_cookie_secure,path="/api/v1/store")
    return owner.token_hash


@router.get("/config")
async def config(session=Depends(store_db,scope="function")):
    settings = await session.get(AdminSettings,1)
    return {"shop_name":settings.shop_name if settings else "Commerce Lab",
            "contact_email":settings.contact_email if settings else "",
            "shipping_fee":get_settings().shipping_fee_vnd,"currency":"VND","demo":True}


@router.get("/categories")
async def categories(session=Depends(store_db,scope="function")):
    rows = (await session.execute(select(Category,func.count(Product.id)).join(Product).where(
        Product.tenant_id==tenant(),Product.is_active.is_(True),
    ).group_by(Category.id).order_by(Category.name))).all()
    return [{"id":str(c.id),"name":c.name,"slug":c.slug,"count":n} for c,n in rows]


@router.get("/products")
async def products(q:str=Query("",max_length=200),category:str=Query("",max_length=120),
                   min_price:int=Query(0,ge=0),max_price:int|None=Query(None,ge=0),in_stock:bool=False,
                   sort:Literal["latest","price_asc","price_desc"]="latest",page:int=Query(1,ge=1),limit:int=Query(12,ge=1,le=60),
                   session=Depends(store_db,scope="function")):
    if max_price is not None and max_price<min_price:
        raise HTTPException(422,"Khoảng giá chưa hợp lệ.")
    filters=[Product.tenant_id==tenant(),Product.is_active.is_(True)]
    if q.strip():
        term=f"%{q.strip()}%"
        filters.append(or_(Product.name.ilike(term),Product.description.ilike(term),Category.name.ilike(term)))
    if category:
        filters.append(Category.slug==category)
    variant_filters=[ProductVariant.product_id==Product.id,ProductVariant.price>=min_price]
    if max_price is not None:
        variant_filters.append(ProductVariant.price<=max_price)
    if in_stock:
        variant_filters.append(ProductVariant.stock>0)
    filters.append(select(ProductVariant.id).where(*variant_filters).exists())
    base=select(Product,Category).join(Category).where(*filters)
    total=await session.scalar(select(func.count()).select_from(base.subquery()))
    min_price_expr=select(func.min(ProductVariant.price)).where(ProductVariant.product_id==Product.id).correlate(Product).scalar_subquery()
    ordering={"latest":Product.updated_at.desc(),"price_asc":min_price_expr.asc(),"price_desc":min_price_expr.desc()}[sort]
    rows=(await session.execute(base.order_by(ordering,Product.id).offset((page-1)*limit).limit(limit))).all()
    ids=[p.id for p,c in rows]
    variants=(await session.scalars(select(ProductVariant).where(ProductVariant.product_id.in_(ids)).order_by(ProductVariant.sku))).all() if ids else []
    grouped={key:[] for key in ids}
    for v in variants:
        grouped[v.product_id].append(v)
    return {"items":[card(p,c,grouped[p.id]) for p,c in rows],"total":total,"page":page,"limit":limit}


@router.get("/products/{product_id}")
async def product(product_id:UUID,session=Depends(store_db,scope="function")):
    row=(await session.execute(select(Product,Category).join(Category).where(Product.id==product_id,Product.tenant_id==tenant(),Product.is_active.is_(True)))).first()
    if row is None:
        raise HTTPException(404,"Sản phẩm không còn được hiển thị.")
    variants=(await session.scalars(select(ProductVariant).where(ProductVariant.product_id==product_id).order_by(ProductVariant.sku))).all()
    return card(*row,variants)


@router.get("/knowledge")
async def knowledge(session=Depends(store_db,scope="function")):
    rows=(await session.scalars(select(KnowledgeDocument).where(KnowledgeDocument.tenant_id==tenant(),KnowledgeDocument.is_active.is_(True)).order_by(KnowledgeDocument.title))).all()
    return [{"id":str(d.id),"title":d.title,"content":d.content} for d in rows]


@router.get("/cart")
async def cart(owner=Depends(shopper,scope="function"),session=Depends(store_db,scope="function")):
    return await cart_view(session,owner,tenant(),get_settings().shipping_fee_vnd)


@router.put("/cart/items/{variant_id}")
async def update_cart(variant_id:UUID,body:CartUpdate,owner=Depends(shopper,scope="function"),session=Depends(store_db,scope="function")):
    item=await session.scalar(select(CartItem).where(CartItem.session_hash==owner,CartItem.variant_id==variant_id))
    if body.quantity==0:
        if item:
            await session.delete(item)
    else:
        row=(await session.execute(select(ProductVariant,Product).join(Product).where(
            ProductVariant.id==variant_id,Product.tenant_id==tenant(),Product.is_active.is_(True),
        ))).first()
        if row is None:
            raise HTTPException(404,"Không tìm thấy sản phẩm.")
        variant,product=row
        if variant.stock<body.quantity:
            raise HTTPException(409,"Số lượng vượt tồn kho hiện tại.")
        if item:
            item.quantity=body.quantity
        else:
            count=await session.scalar(select(func.count()).select_from(CartItem).where(CartItem.session_hash==owner))
            if count>=50:
                raise HTTPException(409,"Giỏ hàng tối đa 50 biến thể.")
            session.add(CartItem(session_hash=owner,variant_id=variant_id,quantity=body.quantity))
    await session.flush()
    return await cart_view(session,owner,tenant(),get_settings().shipping_fee_vnd)


@router.post("/checkout",status_code=201)
async def place_order(body:CheckoutInput,owner=Depends(customer_owner,scope="function"),session=Depends(store_db,scope="function")):
    return await checkout(session,owner,tenant(),body,get_settings().shipping_fee_vnd)


@router.get("/orders")
async def orders(owner=Depends(customer_owner,scope="function"),session=Depends(store_db,scope="function")):
    rows=(await session.scalars(select(Order).where(Order.session_hash==owner,Order.tenant_id==tenant()).order_by(Order.created_at.desc()).limit(30))).all()
    return [await order_view(session,row) for row in rows]


@router.get("/orders/{code}")
async def get_order(code:str,owner=Depends(customer_owner,scope="function"),session=Depends(store_db,scope="function")):
    order=await session.scalar(select(Order).where(Order.code==code,Order.session_hash==owner,Order.tenant_id==tenant()))
    if order is None:
        raise HTTPException(404,"Không tìm thấy đơn hàng trong tài khoản của bạn.")
    return await order_view(session,order)


@router.post("/chat")
async def chat(body:StoreChatInput,request:Request,user=Depends(require_customer,scope="function")):
    same_origin(request)
    from app.chatbot.customer_assistant import private_reply
    personal = await private_reply(request.app.state.db_sessions, body, user, tenant())
    if personal is not None:
        return personal
    from app.chatbot.store_assistant import StoreAssistant
    return await StoreAssistant(request.app.state.db_sessions,request.app.state.embedding,request.app.state.chat).reply(body,tenant())
