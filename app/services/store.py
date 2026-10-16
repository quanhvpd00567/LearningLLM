"""Shopper-owned carts and atomic COD checkout. Never trust client prices."""
from hashlib import sha256
from decimal import Decimal
import json
import secrets
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, select

from app.db.models import CartItem, Order, OrderItem, Product, ProductVariant


def amount(value):
    return format(Decimal(value), "f")


def card(product, category, variants):
    return {"id":str(product.id), "name":product.name, "description":product.description,
            "category":category.name, "category_slug":category.slug, "category_id":str(category.id),
            "attributes":product.attributes,
            "min_price":amount(min((v.price for v in variants), default=0)),
            "stock":sum(v.stock for v in variants),
            "variants":[{"id":str(v.id), "sku":v.sku, "options":v.options,
                         "price":amount(v.price), "stock":v.stock} for v in variants]}


async def cart_view(session, owner, tenant, shipping_fee):
    rows = (await session.execute(select(CartItem, ProductVariant, Product).join(
        ProductVariant, CartItem.variant_id == ProductVariant.id,
    ).join(Product, ProductVariant.product_id == Product.id).where(
        CartItem.session_hash == owner, Product.tenant_id == tenant,
    ).order_by(CartItem.id))).all()
    items = [{"variant_id":str(v.id), "product_id":str(p.id), "name":p.name,
              "sku":v.sku, "options":v.options, "price":amount(v.price), "stock":v.stock,
              "quantity":item.quantity, "available":p.is_active and v.stock >= item.quantity,
              "line_total":amount(v.price * item.quantity)} for item,v,p in rows]
    subtotal = sum(v.price * item.quantity for item,v,p in rows)
    fee = shipping_fee if items else 0
    return {"items":items,"subtotal":amount(subtotal),"shipping_fee":amount(fee),"total":amount(subtotal+fee)}


async def order_view(session, order):
    items = (await session.scalars(select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.id))).all()
    return {"id":str(order.id),"code":order.code,"status":order.status,"created_at":order.created_at,
            "customer_name":order.customer_name,"phone":order.phone,"address":order.address,"note":order.note,
            "payment_method":"cod","subtotal":amount(order.subtotal),"shipping_fee":amount(order.shipping_fee),"total":amount(order.total),
            "items":[{"name":i.product_name,"sku":i.sku,"options":i.options,
                      "unit_price":amount(i.unit_price),"quantity":i.quantity} for i in items]}


async def checkout(session, owner, tenant, body, shipping_fee):
    request_hash = sha256(json.dumps(body.model_dump(mode="json", exclude={"idempotency_key"}),sort_keys=True).encode()).hexdigest()
    previous = await session.scalar(select(Order).where(Order.session_hash==owner, Order.idempotency_key==body.idempotency_key))
    if previous:
        if previous.request_hash != request_hash:
            raise HTTPException(409,"Mã đặt hàng đã được dùng cho thông tin khác. Vui lòng tải lại.")
        return await order_view(session, previous)
    cart = (await session.scalars(select(CartItem).where(CartItem.session_hash==owner).order_by(CartItem.variant_id))).all()
    if not cart:
        raise HTTPException(409,"Giỏ hàng đang trống.")
    variant_ids = [i.variant_id for i in cart]
    product_ids = select(ProductVariant.product_id).where(ProductVariant.id.in_(variant_ids))
    # Follow the same product -> variant lock order as the admin writers.
    products = {p.id:p for p in (await session.scalars(select(Product).where(Product.id.in_(product_ids)).order_by(Product.id).with_for_update())).all()}
    variants = {v.id:v for v in (await session.scalars(select(ProductVariant).where(ProductVariant.id.in_(variant_ids)).order_by(ProductVariant.id).with_for_update())).all()}
    subtotal = 0
    for item in cart:
        variant = variants.get(item.variant_id)
        product = products.get(variant.product_id) if variant else None
        if not product or product.tenant_id != tenant or not product.is_active:
            raise HTTPException(409,"Có sản phẩm không còn được bán. Vui lòng cập nhật giỏ hàng.")
        if variant.stock < item.quantity:
            raise HTTPException(409,f"{product.name} không đủ tồn kho. Vui lòng điều chỉnh số lượng.")
        subtotal += variant.price * item.quantity
    order = Order(id=uuid4(),code="CL-"+secrets.token_hex(6).upper(),tenant_id=tenant,session_hash=owner,
                  idempotency_key=body.idempotency_key,request_hash=request_hash,
                  customer_name=body.customer_name,phone=body.phone,address=body.address,note=body.note,
                  subtotal=subtotal,shipping_fee=shipping_fee,total=subtotal+shipping_fee,status="pending")
    session.add(order)
    await session.flush()
    for item in cart:
        variant = variants[item.variant_id]
        variant.stock -= item.quantity
        session.add(OrderItem(order_id=order.id,variant_id=variant.id,product_name=products[variant.product_id].name,
                              sku=variant.sku,options=variant.options,unit_price=variant.price,quantity=item.quantity))
    await session.execute(delete(CartItem).where(CartItem.session_hash==owner))
    await session.flush()
    return await order_view(session,order)
