# src/app/schemas.py
from pydantic import BaseModel, EmailStr, constr


class UserCreate(BaseModel):
    email: EmailStr
    password: constr(min_length=8)


class UserRead(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    group_id: int

    class Config:
        orm_mode = True


class ActivationSchema(BaseModel):
    token: str


class EmailSchema(BaseModel):
    email: EmailStr


class TokenSchema(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefreshSchema(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    sub: str
    exp: int


class PasswordResetRequestSchema(BaseModel):
    email: EmailStr


class PasswordResetSchema(BaseModel):
    token: str
    new_password: constr(min_length=8)
