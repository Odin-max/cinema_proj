from datetime import datetime
from decimal import Decimal
import os
from typing import List

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.responses import HTMLResponse

from app.core.security import get_current_admin, get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.models.cart_models import CartItemModel, CartModel
from app.models.movie_models import MovieModel
from app.models.order_models import OrderItemModel, OrderModel
from app.schemas.cart_schema import CartItemCreate, CartItemRead, CartRead

from dotenv import load_dotenv

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


router = APIRouter(prefix="/cart", tags=["cart"])
admin_router = APIRouter(
    prefix="/admin/carts",
    tags=["admin"],
    dependencies=[Depends(get_current_admin)],
)


async def get_or_create_cart(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CartModel:
    q = await db.execute(select(CartModel).where(CartModel.user_id == current_user.id))
    cart = q.scalar_one_or_none()
    if not cart:
        cart = CartModel(user_id=current_user.id)
        db.add(cart)
        await db.commit()
        await db.refresh(cart)
    return cart


@router.post("/items", response_model=CartRead, status_code=status.HTTP_201_CREATED)
async def add_to_cart(
    data: CartItemCreate,
    cart: CartModel = Depends(get_or_create_cart),
    db: AsyncSession = Depends(get_db),
):
    cnt = await db.scalar(
        select(func.count())
        .select_from(CartItemModel)
        .where(
            CartItemModel.cart_id == cart.id,
            CartItemModel.movie_id == data.movie_id,
        )
    )
    if cnt:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Movie already in cart")

    movie = await db.get(MovieModel, data.movie_id)
    if not movie:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Movie not found")

    item = CartItemModel(
        cart_id=cart.id,
        movie_id=movie.id,
        added_at=datetime.utcnow(),
    )
    db.add(item)
    await db.commit()

    return await _load_and_build_cart(cart.id, db)


@router.delete("/items/{movie_id}", response_model=CartRead)
async def remove_from_cart(
    movie_id: int,
    cart: CartModel = Depends(get_or_create_cart),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        delete(CartItemModel).where(
            CartItemModel.cart_id == cart.id,
            CartItemModel.movie_id == movie_id,
        )
    )
    await db.commit()
    return await _load_and_build_cart(cart.id, db)


@router.get("/", response_model=CartRead)
async def view_cart(
    cart: CartModel = Depends(get_or_create_cart),
    db: AsyncSession = Depends(get_db),
):
    return await _load_and_build_cart(cart.id, db)


@router.delete("/clear", response_model=CartRead)
async def clear_cart(
    cart: CartModel = Depends(get_or_create_cart),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(delete(CartItemModel).where(CartItemModel.cart_id == cart.id))
    await db.commit()
    return await _load_and_build_cart(cart.id, db)


@router.post("/checkout", response_class=HTMLResponse)
async def checkout(
    request: Request,
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
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Your bin is empty")

    line_items = []
    total = Decimal(0)
    for ci in cart.items:
        price = Decimal(ci.movie.price)
        total += price * ci.quantity
        line_items.append(
            {
                "price_data": {
                    "currency": "usd",
                    "unit_amount": int(price * 100),
                    "product_data": {"name": ci.movie.name},
                },
                "quantity": ci.quantity,
            }
        )

    order = OrderModel(user_id=current_user.id, total_amount=total)
    db.add(order)
    await db.flush()

    for ci in cart.items:
        db.add(
            OrderItemModel(
                order_id=order.id,
                movie_id=ci.movie_id,
                price_at_order=Decimal(ci.movie.price),
            )
        )

    await db.execute(delete(CartItemModel).where(CartItemModel.cart_id == cart.id))
    await db.commit()

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            success_url="http://localhost:8000/cart/orders/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="http://localhost:8000/cart",
            metadata={"order_id": str(order.id)},
        )
    except stripe.error.InvalidRequestError as e:
        msg = getattr(e, "user_message", None) or e.__str__()
        content = "Mininum amount is 0.5€"
        return HTMLResponse(content, status_code=status.HTTP_400_BAD_REQUEST)

    return JSONResponse({"checkout_url": session.url})


@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except ValueError as e:
        print("Webhook payload error:", e)
        return Response(status_code=status.HTTP_400_BAD_REQUEST)
    except stripe.error.SignatureVerificationError as e:
        print("Webhook signature verification failed:", e)
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    print("Webhook verified, event type:", event.type)

    if event.type == "checkout.session.completed":
        sess = event.data.object
        order_id = int(sess.metadata.get("order_id", 0))
        print(f"→ Marking order #{order_id} as paid…")
        try:
            await db.execute(
                update(OrderModel)
                .where(OrderModel.id == order_id)
                .values(status="paid")
            )
            await db.commit()
            updated = await db.get(OrderModel, order_id)
            print(f"→ Order #{order_id} status is now:", updated.status)
        except Exception as e:
            print("Failed to update order status:", e)
    return Response(status_code=status.HTTP_200_OK)


@router.get("/orders/success", response_class=HTMLResponse)
async def order_success(session_id: str, db: AsyncSession = Depends(get_db)):
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except stripe.error.StripeError:
        raise HTTPException(404, "Session not found")

    order_id = int(session.metadata.get("order_id", 0))
    result = await db.execute(
        select(OrderModel)
        .options(selectinload(OrderModel.items))
        .where(OrderModel.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")

    html = f"""
    <html>
      <head><title>Successful Payment</title></head>
      <body style="font-family:sans-serif; text-align:center; padding:2rem;">
        <h1 style="color:green;">✅ Thank you! Payment was successful.</h1>
        <p> Your order #{order.id} now is in status <strong>Paid</strong>.</p>
        <a href="/movies" style="color:#007bff;"> Return to catalog</a>
      </body>
    </html>
    """
    return HTMLResponse(html)


async def _load_and_build_cart(cart_id: int, db: AsyncSession) -> CartRead:
    q = await db.execute(
        select(CartItemModel)
        .options(selectinload(CartItemModel.movie).selectinload(MovieModel.genres))
        .where(CartItemModel.cart_id == cart_id)
    )
    items_raw: List[CartItemModel] = q.scalars().all()

    items: List[CartItemRead] = []
    for ci in items_raw:
        m = ci.movie
        items.append(
            CartItemRead(
                id=ci.id,
                movie_id=m.id,
                title=m.name,
                price=m.price,
                genres=[g.name for g in m.genres],
                year=m.year,
                added_at=ci.added_at,
            )
        )
    cart = await db.get(CartModel, cart_id)

    return CartRead(
        id=cart.id,
        user_id=cart.user_id,
        items=items,
    )
