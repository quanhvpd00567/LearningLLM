from datetime import timedelta
from hashlib import sha256
import secrets
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.customer_auth import (COOKIE, COOKIE_PATH, create_customer_session, hash_password,
    public_customer, require_customer, store_db, verify_password)
from app.db.models import Customer, CustomerAuthLimit, CustomerSession, ShopperSession
from app.schemas.store import CustomerLogin, CustomerRegister

router = APIRouter(prefix="/store/auth", tags=["Customer authentication"])
# Equal work for unknown-email login attempts, without storing a default credential.
DUMMY_HASH = "scrypt$32768$8$3$" + "00"*16 + "$" + "00"*64


async def auth_limit(request: Request):
    """Persist limits outside the credential transaction, including rejected logins."""
    from app.core.admin_auth import same_origin
    same_origin(request)
    address = request.client.host if request.client else "unknown"
    key = sha256((get_settings().admin_tenant_id + ":" + address).encode()).hexdigest()
    # Do not trust X-Forwarded-For supplied by a caller.
    async with request.app.state.db_sessions.begin() as session:
        now = await session.scalar(select(func.clock_timestamp()))
        await session.execute(delete(CustomerAuthLimit).where(CustomerAuthLimit.expires_at <= now))
        row = await session.scalar(insert(CustomerAuthLimit).values(key=key, attempts=1, expires_at=now+timedelta(minutes=15))
            .on_conflict_do_update(index_elements=[CustomerAuthLimit.key], set_={"attempts": CustomerAuthLimit.attempts+1})
            .returning(CustomerAuthLimit))
        blocked = row.attempts > 30
    if blocked:
        raise HTTPException(429, "Quá nhiều lần đăng nhập/đăng ký. Vui lòng thử lại sau 15 phút.")


@router.post("/register", status_code=201, dependencies=[Depends(auth_limit)])
async def register(body: CustomerRegister, request: Request, response: Response, session=Depends(store_db, scope="function")):
    response.headers["Cache-Control"] = "no-store"
    tenant = get_settings().admin_tenant_id
    if await session.scalar(select(Customer.id).where(Customer.tenant_id==tenant, Customer.email==body.email)):
        raise HTTPException(409, "Không thể đăng ký email này. Hãy đăng nhập hoặc dùng email khác.")
    password_hash = await run_in_threadpool(hash_password, body.password)
    now = await session.scalar(select(func.clock_timestamp()))
    owner = ShopperSession(token_hash=sha256(secrets.token_bytes(48)).hexdigest(), expires_at=now+timedelta(days=36500))
    session.add(owner)
    await session.flush()
    user = Customer(id=uuid4(), tenant_id=tenant, email=body.email, name=body.name, password_hash=password_hash, owner_hash=owner.token_hash)
    session.add(user)
    await session.flush()
    await create_customer_session(user, request, response, session)
    return public_customer(user)


@router.post("/login", dependencies=[Depends(auth_limit)])
async def login(body: CustomerLogin, request: Request, response: Response, session=Depends(store_db, scope="function")):
    response.headers["Cache-Control"] = "no-store"
    user = await session.scalar(select(Customer).where(Customer.tenant_id==get_settings().admin_tenant_id, Customer.email==body.email))
    valid = await run_in_threadpool(verify_password, body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(401, "Email hoặc mật khẩu chưa đúng.")
    await create_customer_session(user, request, response, session)
    return public_customer(user)


@router.get("/me")
async def me(user=Depends(require_customer, scope="function")):
    return public_customer(user)


@router.post("/logout")
async def logout(request: Request, response: Response, session=Depends(store_db, scope="function")):
    token = request.cookies.get(COOKIE)
    if token:
        await session.execute(delete(CustomerSession).where(CustomerSession.token_hash==sha256(token.encode()).hexdigest()))
    response.delete_cookie(COOKIE, path=COOKIE_PATH, secure=get_settings().store_cookie_secure, httponly=True, samesite="strict")
    return {"ok": True}
