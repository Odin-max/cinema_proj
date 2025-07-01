from app.schemas.cart_schema import CartRead
from pydantic import BaseModel


class CheckoutResponse(BaseModel):
    client_secret: str
    cart: CartRead

    model_config = {"from_attributes": True}
