"""Single administrator, opaque database-backed sessions, no external auth service."""
from datetime import timedelta
from hashlib import sha256
import secrets

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.config import get_settings
from app.db.models import AdminSession

COOKIE = "commerce_admin_session"
SESSION_SECONDS = 8 * 60 * 60


def same_origin(request: Request):
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Yêu cầu phải đến từ trang quản trị hiện tại.")


async def admin_db(request: Request):
    try:
        async with request.app.state.db_sessions.begin() as session:
            yield session
    except IntegrityError as exc:
        raise HTTPException(409, "Dữ liệu bị trùng hoặc đang được sử dụng. Hãy tải lại và kiểm tra.") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Không kết nối được dữ liệu quản trị.") from exc


async def require_admin(request: Request, session=Depends(admin_db, scope="function")):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        same_origin(request)
    settings = get_settings()
    if not settings.admin_password.get_secret_value():
        raise HTTPException(503, "Chưa cấu hình ADMIN_PASSWORD cho trang quản trị.")
    token = request.cookies.get(COOKIE, "")
    auth = await session.get(AdminSession, sha256(token.encode()).hexdigest()) if token else None
    now = await session.scalar(select(func.clock_timestamp()))
    if auth is None or auth.expires_at <= now or auth.username != settings.admin_username:
        raise HTTPException(401, "Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.")
    return auth.username


async def create_session(username: str, session, response: Response):
    settings = get_settings()
    now = await session.scalar(select(func.clock_timestamp()))
    await session.execute(delete(AdminSession).where(AdminSession.expires_at <= now))
    token = secrets.token_urlsafe(48)
    session.add(AdminSession(token_hash=sha256(token.encode()).hexdigest(), username=username,
                             expires_at=now + timedelta(seconds=SESSION_SECONDS)))
    response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True,
                        secure=settings.admin_cookie_secure, samesite="strict", path="/api/v1/admin")
