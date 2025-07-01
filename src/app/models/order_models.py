from sqlalchemy import (
    Column,
    Integer,
    ForeignKey,
    DateTime,
    Enum,
    Numeric,
    func,
)
from sqlalchemy.orm import relationship
import enum
from app.db.base import Base
from .movie_models import MovieModel


class OrderStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    canceled = "canceled"


class OrderModel(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status = Column(
        Enum(OrderStatus), nullable=False, server_default=OrderStatus.pending.value
    )
    total_amount = Column(Numeric(10, 2), nullable=False)

    user = relationship("User", back_populates="orders")
    items = relationship(
        "OrderItemModel", back_populates="order", cascade="all, delete-orphan"
    )


class OrderItemModel(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    movie_id = Column(Integer, ForeignKey("movies.id"), nullable=False)
    price_at_order = Column(Numeric(10, 2), nullable=False)

    order = relationship("OrderModel", back_populates="items")
    movie = relationship("MovieModel")
