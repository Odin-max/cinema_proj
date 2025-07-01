from datetime import datetime
from sqlalchemy import Column, Integer, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.user_models import User


from .movie_models import MovieModel


class CartModel(Base):
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="cart")
    items = relationship(
        "CartItemModel",
        back_populates="cart",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )


class CartItemModel(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "movie_id", name="uq_cart_movie"),)

    id = Column(Integer, primary_key=True, index=True)
    cart_id = Column(
        Integer, ForeignKey("carts.id", ondelete="CASCADE"), nullable=False
    )
    movie_id = Column(
        Integer, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    quantity = Column(Integer, default=1, nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)

    cart = relationship("CartModel", back_populates="items")
    movie = relationship("MovieModel")


User.cart = relationship("CartModel", back_populates="user", uselist=False)
