# app/schemas/cart_schema.py
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class CartItemCreate(BaseModel):
    movie_id: int


class CartItemRead(BaseModel):
    id: int
    movie_id: int
    title: str
    price: Optional[float]
    genres: List[str]
    year: int
    added_at: datetime

    model_config = {"from_attributes": True}


class CartRead(BaseModel):
    id: int
    user_id: int
    items: List[CartItemRead]

    model_config = {"from_attributes": True}
