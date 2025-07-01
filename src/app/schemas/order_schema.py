# src/app/schemas/order_schema.py

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict
from typing import List

class OrderStatus(str, Enum):
    pending = "pending"
    paid = "paid"
    canceled = "canceled"

class OrderItemRead(BaseModel):
    id: int
    movie_id: int
    price_at_order: float

    model_config = ConfigDict(from_attributes=True)

class OrderRead(BaseModel):
    id: int
    created_at: datetime
    status: OrderStatus
    total_amount: float
    items: List[OrderItemRead]

    model_config = ConfigDict(from_attributes=True)
