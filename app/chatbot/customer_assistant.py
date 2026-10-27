"""Private answers come from ownership-filtered SQL, never a model-selected user ID.

Private query results are never indexed into shared RAG or passed to the model
by this handler. Private intent is answered deterministically.
"""
import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import Order
from app.services.store import order_view

STATUS = {"pending": "Chờ xác nhận", "confirmed": "Đã xác nhận", "shipping": "Đang giao",
          "completed": "Hoàn tất", "cancelled": "Đã hủy"}


def reply(message):
    return {"message": message, "products": [], "sources": [], "degraded": False, "private": True}


async def private_reply(sessions, body, user, tenant):
    current = body.messages[-1].content
    if re.search(r"thông tin (?:tài khoản|cá nhân)|email của|tên của tôi|tôi là ai", current, re.I):
        return reply(f"Tài khoản của bạn: {user.name}. Email: {user.email}.")
    if not re.search(r"đơn|\border\b|lịch sử mua|đã mua|mua những gì|CL-[0-9a-f]+|địa chỉ (?:giao|nhận)", current, re.I):
        return None
    code = re.search(r"\bCL-[0-9a-z]+\b", current, re.I)
    try:
        async with sessions() as session:
            stmt = select(Order).where(Order.session_hash == user.owner_hash, Order.tenant_id == tenant)
            if code:
                stmt = stmt.where(Order.code == code.group().upper())
            orders = (await session.scalars(stmt.order_by(Order.created_at.desc(), Order.id).limit(10))).all()
            if not orders:
                return reply("Không tìm thấy đơn hàng này trong tài khoản của bạn." if code else "Tài khoản của bạn chưa có đơn hàng.")
            lines = []
            for order in orders:
                view = await order_view(session, order)
                items = "; ".join(f"{item['name']} × {item['quantity']}" for item in view["items"])
                total = f"{order.total:,.0f}".replace(",", ".")
                lines.append(f"• {order.code} · {STATUS.get(order.status, order.status)} · {total} đ\n  {items}")
            return reply(("Đơn hàng của bạn:\n" if code else "Tối đa 10 đơn hàng gần nhất của bạn:\n") + "\n".join(lines))
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Chưa lấy được đơn hàng của bạn. Vui lòng thử lại.") from exc
