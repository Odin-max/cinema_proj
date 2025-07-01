# src/app/routes/orders.py
from typing import List, Optional
from sqlalchemy.orm import selectinload
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from app.db.session import get_db
from app.models.order_models import OrderModel, OrderItemModel, OrderStatus
from app.models.cart_models import CartItemModel, CartModel
from app.schemas.order_schema import OrderRead
from app.core.security import get_current_user

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def place_order(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CartModel)
        .options(selectinload(CartModel.items).selectinload(CartItemModel.movie))
        .where(CartModel.user_id == current_user.id)
    )
    cart = result.scalar_one_or_none()
    if not cart or not cart.items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Cart is empty")

    order_items_data = []
    total = Decimal(0)
    for ci in cart.items:
        price = ci.movie.price
        order_items_data.append({"movie_id": ci.movie_id, "price_at_order": price})
        total += Decimal(price)

    order = OrderModel(user_id=current_user.id, total_amount=total)
    db.add(order)
    await db.flush()

    for it in order_items_data:
        db.add(OrderItemModel(order_id=order.id, **it))

    await db.execute(delete(CartItemModel).where(CartItemModel.cart_id == cart.id))

    await db.commit()

    result = await db.execute(
        select(OrderModel)
        .options(selectinload(OrderModel.items).selectinload(OrderItemModel.movie))
        .where(OrderModel.id == order.id)
    )
    order_with_items = result.scalar_one()

    return order_with_items


@router.get("/", response_model=List[OrderRead], status_code=status.HTTP_200_OK)
async def list_user_orders(
    status: Optional[OrderStatus] = Query(
        None, description="Filter by order status (`pending`, `paid`, `canceled`)"
    ),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(OrderModel)
        .options(selectinload(OrderModel.items).selectinload(OrderItemModel.movie))
        .where(OrderModel.user_id == current_user.id)
    )

    if status is not None:
        stmt = stmt.where(OrderModel.status == status)

    stmt = stmt.order_by(OrderModel.created_at.desc())

    result = await db.execute(stmt)
    orders = result.scalars().all()
    return orders


@router.post("/orders/{order_id}/cancel", response_model=OrderRead)
async def cancel_order(
    order_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OrderModel).where(
            OrderModel.id == order_id, OrderModel.user_id == current_user.id
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.status = "canceled"
    await db.commit()

    result = await db.execute(
        select(OrderModel)
        .options(selectinload(OrderModel.items).selectinload(OrderItemModel.movie))
        .where(OrderModel.id == order_id)
    )
    order_with_items = result.scalar_one()

    return order_with_items
