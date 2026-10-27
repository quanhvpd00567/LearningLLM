from hashlib import sha256
import secrets
import logging
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert

from app.chatbot.rag.chunking import PIPELINE_VERSION
from app.core.admin_auth import COOKIE, admin_db, create_session, require_admin, same_origin
from app.core.config import get_settings
from app.db.models import AdminSession, AdminSettings, Category, DocumentChunk, Job, KnowledgeDocument, Product, ProductVariant
from app.schemas.admin import CategoryInput, KnowledgeWrite, LoginInput, ProductWrite, SiteSettingsInput
from app.schemas.sources import KnowledgeInput, ProductInput
from app.services.sources import SourceService
from scripts.reindex import reindex

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(require_admin, scope="function")])
auth_router = APIRouter(prefix="/admin/auth", tags=["Admin auth"])


def tenant():
    return get_settings().admin_tenant_id


def source_service(session):
    return SourceService(session, get_settings().embedding_model, tenant())


def product_data(product, category, variants):
    return {"id": str(product.id), "name": product.name, "description": product.description,
            "category_id": str(product.category_id), "category": category,
            "attributes": product.attributes, "is_active": product.is_active,
            "source_version": product.source_version, "updated_at": product.updated_at,
            "variants": [{"id": str(v.id), "sku": v.sku, "options": v.options,
                          "price": str(v.price), "stock": v.stock} for v in variants]}


async def product_detail(session, product):
    category = await session.get(Category, product.category_id)
    variants = (await session.scalars(select(ProductVariant).where(ProductVariant.product_id == product.id).order_by(ProductVariant.sku))).all()
    await session.refresh(product)
    return product_data(product, category.name if category else "", variants)


@auth_router.post("/login")
async def login(body: LoginInput, request: Request, response: Response, session=Depends(admin_db, scope="function")):
    same_origin(request)
    settings = get_settings()
    password = settings.admin_password.get_secret_value()
    if not password:
        raise HTTPException(503, "Chưa cấu hình ADMIN_PASSWORD cho trang quản trị.")
    if not (secrets.compare_digest(body.username.encode(), settings.admin_username.encode())
            & secrets.compare_digest(body.password.encode(), password.encode())):
        logging.getLogger("app.auth").warning("admin_login_failed")
        raise HTTPException(401, "Tên đăng nhập hoặc mật khẩu chưa đúng.")
    await create_session(body.username, session, response)
    logging.getLogger("app.auth").info("admin_login_success")
    return {"username": body.username}


@auth_router.get("/me")
async def me(username=Depends(require_admin, scope="function")):
    return {"username": username}


@auth_router.post("/logout", dependencies=[Depends(require_admin, scope="function")])
async def logout(request: Request, response: Response, session=Depends(admin_db, scope="function")):
    token = request.cookies.get(COOKIE, "")
    await session.execute(delete(AdminSession).where(AdminSession.token_hash == sha256(token.encode()).hexdigest()))
    response.delete_cookie(COOKIE, path="/api/v1/admin")
    logging.getLogger("app.auth").info("admin_logout")
    return {"ok": True}


async def settings_values(session):
    value = await session.get(AdminSettings, 1)
    return {"shop_name": value.shop_name if value else "Commerce Lab",
            "contact_email": value.contact_email if value else "",
            "low_stock_threshold": value.low_stock_threshold if value else 5,
            "embedding_paused": value.embedding_paused if value else False}


@router.get("/settings")
async def get_settings_view(session=Depends(admin_db, scope="function")):
    settings = get_settings()
    return {**await settings_values(session), "runtime": {
        "embedding_model": settings.embedding_model, "embedding_dimensions": settings.embedding_dimensions,
        "chat_model": settings.gemini_model, "pipeline_version": PIPELINE_VERSION,
        "batch_size": settings.embedding_batch_size, "poll_seconds": settings.embedding_job_poll_seconds,
        "lease_seconds": settings.embedding_job_lease_seconds, "currency": "VND",
    }}


@router.put("/settings")
async def save_settings(body: SiteSettingsInput, session=Depends(admin_db, scope="function")):
    stmt = insert(AdminSettings).values(id=1, **body.model_dump())
    await session.execute(stmt.on_conflict_do_update(index_elements=[AdminSettings.id], set_={**body.model_dump(), "updated_at": func.now()}))
    return {"ok": True}


@router.get("/overview")
async def overview(session=Depends(admin_db, scope="function")):
    config = await settings_values(session)
    count = lambda stmt: session.scalar(stmt)
    products = await count(select(func.count()).select_from(Product).where(Product.tenant_id == tenant()))
    active = await count(select(func.count()).select_from(Product).where(Product.tenant_id == tenant(), Product.is_active.is_(True)))
    documents = await count(select(func.count()).select_from(KnowledgeDocument).where(KnowledgeDocument.tenant_id == tenant()))
    variants = await count(select(func.count()).select_from(ProductVariant).join(Product).where(Product.tenant_id == tenant()))
    low_stock = await count(select(func.count()).select_from(ProductVariant).join(Product).where(
        Product.tenant_id == tenant(), Product.is_active.is_(True), ProductVariant.stock <= config["low_stock_threshold"]))
    chunks = await count(select(func.count()).select_from(DocumentChunk).where(
        DocumentChunk.tenant_id == tenant(), DocumentChunk.status == "current",
        DocumentChunk.embedding_model == get_settings().embedding_model, DocumentChunk.pipeline_version == PIPELINE_VERSION))
    jobs = dict((await session.execute(scoped_jobs(select(Job.status, func.count()).group_by(Job.status)))).all())
    return {"products": products, "active_products": active, "documents": documents,
            "variants": variants, "low_stock": low_stock, "chunks": chunks, "jobs": jobs, **config}


@router.get("/categories")
async def categories(session=Depends(admin_db, scope="function")):
    rows = (await session.execute(select(Category, func.count(Product.id)).outerjoin(
        Product, (Product.category_id == Category.id) & (Product.tenant_id == tenant()),
    ).group_by(Category.id).order_by(Category.name))).all()
    return [{"id": str(c.id), "name": c.name, "slug": c.slug, "product_count": n} for c, n in rows]


@router.post("/categories", status_code=201)
async def create_category(body: CategoryInput, session=Depends(admin_db, scope="function")):
    item = Category(id=uuid4(), **body.model_dump())
    session.add(item)
    await session.flush()
    return {"id": str(item.id)}


@router.put("/categories/{category_id}")
async def update_category(category_id: UUID, body: CategoryInput, session=Depends(admin_db, scope="function")):
    category = await session.get(Category, category_id, with_for_update=True)
    if category is None:
        raise HTTPException(404, "Không tìm thấy danh mục.")
    if category.name != body.name or category.slug != body.slug:
        category.name, category.slug = body.name, body.slug
        products = (await session.scalars(select(Product).where(Product.category_id == category.id).order_by(Product.id).with_for_update())).all()
        for product in products:
            product.source_version += 1
            await session.flush()
            await SourceService(session, get_settings().embedding_model, product.tenant_id)._enqueue("product", product)
    return {"ok": True}


@router.get("/products")
async def products(q: str = Query("", max_length=200), active: Literal["all", "active", "inactive"] = "all",
                   page: int = Query(1, ge=1), limit: int = Query(12, ge=1, le=100), session=Depends(admin_db, scope="function")):
    conditions = [Product.tenant_id == tenant()]
    if q.strip():
        conditions.append(Product.name.ilike(f"%{q.strip()}%"))
    if active != "all":
        conditions.append(Product.is_active.is_(active == "active"))
    total = await session.scalar(select(func.count()).select_from(Product).where(*conditions))
    rows = (await session.execute(select(Product, Category.name).join(Category).where(*conditions)
                                  .order_by(Product.updated_at.desc(), Product.id).offset((page - 1) * limit).limit(limit))).all()
    ids = [p.id for p, _ in rows]
    variants = (await session.scalars(select(ProductVariant).where(ProductVariant.product_id.in_(ids)).order_by(ProductVariant.sku))).all() if ids else []
    by_product = {key: [] for key in ids}
    for variant in variants:
        by_product[variant.product_id].append(variant)
    return {"total": total, "page": page, "limit": limit,
            "items": [product_data(p, category, by_product[p.id]) for p, category in rows]}


@router.get("/products/{product_id}")
async def get_product(product_id: UUID, session=Depends(admin_db, scope="function")):
    product = await session.scalar(select(Product).where(Product.id == product_id, Product.tenant_id == tenant()))
    if product is None:
        raise HTTPException(404, "Không tìm thấy sản phẩm.")
    return await product_detail(session, product)


async def write_product(session, product_id, body, existing=False):
    service = source_service(session)
    if existing:
        current = await service._locked(Product, product_id)
        if current is None:
            raise HTTPException(404, "Không tìm thấy sản phẩm.")
        if body.expected_version != current.source_version:
            raise HTTPException(409, "Sản phẩm đã được cập nhật. Hãy tải lại trước khi lưu.")
    try:
        product = await service.save_product(product_id, ProductInput(**body.model_dump(exclude={"variants", "expected_version"})))
        variants = (await session.scalars(select(ProductVariant).where(ProductVariant.product_id == product_id))).all()
        wanted = {v.sku for v in body.variants}
        removed = [v for v in variants if v.sku not in wanted]
        for variant in removed:
            await session.delete(variant)
        if removed:
            product.source_version += 1
            await session.flush()
            await service._enqueue("product", product)
        for variant in body.variants:
            await service.save_variant(product_id, variant)
        return await product_detail(session, product)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/products", status_code=201)
async def create_product(body: ProductWrite, session=Depends(admin_db, scope="function")):
    return await write_product(session, uuid4(), body)


@router.put("/products/{product_id}")
async def update_product(product_id: UUID, body: ProductWrite, session=Depends(admin_db, scope="function")):
    return await write_product(session, product_id, body, existing=True)


@router.get("/knowledge")
async def knowledge(q: str = Query("", max_length=200), page: int = Query(1, ge=1), limit: int = Query(12, ge=1, le=100), session=Depends(admin_db, scope="function")):
    conditions = [KnowledgeDocument.tenant_id == tenant()]
    if q.strip():
        conditions.append(KnowledgeDocument.title.ilike(f"%{q.strip()}%"))
    total = await session.scalar(select(func.count()).select_from(KnowledgeDocument).where(*conditions))
    items = (await session.scalars(select(KnowledgeDocument).where(*conditions).order_by(KnowledgeDocument.updated_at.desc(), KnowledgeDocument.id)
                                  .offset((page - 1) * limit).limit(limit))).all()
    return {"total": total, "items": [{"id": str(d.id), "title": d.title, "content": d.content,
            "is_active": d.is_active, "source_version": d.source_version, "updated_at": d.updated_at} for d in items]}


async def write_knowledge(session, source_id, body, existing=False):
    service = source_service(session)
    if existing:
        current = await service._locked(KnowledgeDocument, source_id)
        if current is None:
            raise HTTPException(404, "Không tìm thấy tài liệu.")
        if body.expected_version != current.source_version:
            raise HTTPException(409, "Tài liệu đã được cập nhật. Hãy tải lại trước khi lưu.")
    doc = await service.save_knowledge(source_id, KnowledgeInput(**body.model_dump(exclude={"expected_version"})))
    return {"id": str(doc.id), "source_version": doc.source_version}


@router.post("/knowledge", status_code=201)
async def create_knowledge(body: KnowledgeWrite, session=Depends(admin_db, scope="function")):
    return await write_knowledge(session, uuid4(), body)


@router.put("/knowledge/{source_id}")
async def update_knowledge(source_id: UUID, body: KnowledgeWrite, session=Depends(admin_db, scope="function")):
    return await write_knowledge(session, source_id, body, existing=True)


def scoped_jobs(stmt):
    return stmt.outerjoin(Product, (Job.source_type == "product") & (Job.source_id == Product.id)).outerjoin(
        KnowledgeDocument, (Job.source_type == "knowledge") & (Job.source_id == KnowledgeDocument.id),
    ).where(or_(Product.tenant_id == tenant(), KnowledgeDocument.tenant_id == tenant()))


@router.get("/jobs")
async def jobs(status: Literal["all", "pending", "processing", "completed", "failed", "superseded"] = "all",
               page: int = Query(1, ge=1), limit: int = Query(12, ge=1, le=100), session=Depends(admin_db, scope="function")):
    condition = [] if status == "all" else [Job.status == status]
    total = await session.scalar(scoped_jobs(select(func.count()).select_from(Job).where(*condition)))
    rows = (await session.execute(scoped_jobs(select(Job, func.coalesce(Product.name, KnowledgeDocument.title).label("title"))
                .where(*condition)).order_by(Job.created_at.desc(), Job.id).offset((page - 1) * limit).limit(limit))).all()
    return {"total": total, "items": [{"id": str(j.id), "title": title, "source_type": j.source_type,
            "source_version": j.source_version, "status": j.status, "attempts": j.attempts,
            "max_attempts": j.max_attempts, "job_type": j.job_type, "created_at": j.created_at,
            "last_error": j.last_error, "embedding_model": j.embedding_model} for j, title in rows]}


@router.post("/jobs/reindex")
async def reindex_all(request: Request):
    return {"requeued": await reindex(request.app.state.db_sessions, get_settings().embedding_model, tenant_id=tenant())}


@router.post("/jobs/{job_id}/retry")
async def retry_job(job_id: UUID, session=Depends(admin_db, scope="function")):
    initial = await session.get(Job, job_id)
    if initial is None:
        raise HTTPException(404, "Không tìm thấy job.")
    model = Product if initial.source_type == "product" else KnowledgeDocument
    source = await session.scalar(select(model).where(model.id == initial.source_id, model.tenant_id == tenant()).with_for_update())
    if source is None:
        raise HTTPException(404, "Không tìm thấy nguồn của job.")
    job = await session.scalar(select(Job).where(Job.id == job_id).with_for_update().execution_options(populate_existing=True))
    if (job.status != "failed" or job.source_version != source.source_version
        or job.embedding_model != get_settings().embedding_model or job.pipeline_version != PIPELINE_VERSION):
        raise HTTPException(409, "Chỉ retry job lỗi của phiên bản và model hiện tại.")
    job.status, job.attempts = "pending", 0
    job.available_at, job.completed_at, job.last_error = func.clock_timestamp(), None, None
    job.locked_at, job.locked_by = None, None
    return {"ok": True}


@router.get("/orders")
async def admin_orders(page:int=Query(1,ge=1),limit:int=Query(12,ge=1,le=100),session=Depends(admin_db,scope="function")):
    from app.db.models import Order
    from app.services.store import order_view
    total=await session.scalar(select(func.count()).select_from(Order).where(Order.tenant_id==tenant()))
    rows=(await session.scalars(select(Order).where(Order.tenant_id==tenant()).order_by(Order.created_at.desc()).offset((page-1)*limit).limit(limit))).all()
    return {"total":total,"items":[await order_view(session,row) for row in rows]}
