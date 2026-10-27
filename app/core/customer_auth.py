"""Customer identity stays separate from admin and anonymous shopper cookies."""
from datetime import timedelta
from hashlib import sha256, scrypt
import secrets

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.admin_auth import same_origin
from app.core.config import get_settings
from app.db.models import Customer, CustomerSession

COOKIE = "commerce_customer"
COOKIE_PATH = "/api/v1/store"
SESSION_DAYS = 7


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = scrypt(password.encode(), salt=salt, n=32768, r=8, p=3, maxmem=64*1024*1024)
    return "scrypt$32768$8$3$" + salt.hex() + "$" + digest.hex()


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = stored.split("$")
        if (algorithm, n, r, p) != ("scrypt", "32768", "8", "3"):
            return False
        actual = scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), maxmem=64*1024*1024)
        return secrets.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


async def store_db(request: Request):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        same_origin(request)
    try:
        async with request.app.state.db_sessions.begin() as session:
            yield session
    except IntegrityError as exc:
        raise HTTPException(409, "Dữ liệu đã tồn tại hoặc thay đổi. Vui lòng kiểm tra lại.") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Cửa hàng tạm thời chưa kết nối được dữ liệu. Vui lòng thử lại.") from exc


async def optional_customer(request: Request, response: Response, session=Depends(store_db, scope="function")):
    response.headers["Cache-Control"] = "no-store"
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    user = await session.scalar(select(Customer).join(CustomerSession, CustomerSession.customer_id == Customer.id).where(
        CustomerSession.token_hash == sha256(token.encode()).hexdigest(),
        CustomerSession.expires_at > func.clock_timestamp(),
        Customer.tenant_id == get_settings().admin_tenant_id,
    ))
    if user is None:
        raise HTTPException(401, "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.")
    return user


async def require_customer(user=Depends(optional_customer, scope="function")):
    if user is None:
        raise HTTPException(401, "Vui lòng đăng nhập để sử dụng chức năng này.")
    return user


async def customer_owner(user=Depends(require_customer, scope="function"), session=Depends(store_db, scope="function")):
    # Serialize cart/checkout across devices with the same lock used for guest carts.
    from app.db.models import ShopperSession
    await session.scalar(select(ShopperSession).where(ShopperSession.token_hash == user.owner_hash).with_for_update())
    return user.owner_hash


def public_customer(user):
    return {"id": str(user.id), "name": user.name, "email": user.email}


async def create_customer_session(user, request, response, session):
    from sqlalchemy import delete
    token = secrets.token_urlsafe(48)
    old = request.cookies.get(COOKIE)
    if old:
        await session.execute(delete(CustomerSession).where(CustomerSession.token_hash == sha256(old.encode()).hexdigest()))
    now = await session.scalar(select(func.clock_timestamp()))
    session.add(CustomerSession(token_hash=sha256(token.encode()).hexdigest(), customer_id=user.id,
                                expires_at=now + timedelta(days=SESSION_DAYS)))
    response.set_cookie(COOKIE, token, max_age=SESSION_DAYS*86400, httponly=True, samesite="strict",
                        secure=get_settings().store_cookie_secure, path=COOKIE_PATH)
