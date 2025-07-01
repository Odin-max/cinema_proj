from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Cookie, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.user_models import User, UserGroup
from app.schemas.auth_schema import TokenPayload


pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return pwd_ctx.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


async def get_current_user(
    authorization: str = Depends(oauth2_scheme),
    access_token: str | None = Cookie(None, include_in_schema=False),
    db: AsyncSession = Depends(get_db),
):
    token = authorization or access_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY_ACCESS,
            algorithms=[settings.JWT_SIGNING_ALGORITHM],
        )
        token_data = TokenPayload(**payload)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await db.scalar(select(User).where(User.id == int(token_data.sub)))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_moderator(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserGroup.name).where(UserGroup.id == current_user.group_id)
    )
    group_name: str | None = result.scalar_one_or_none()

    if not group_name or group_name.lower() not in ("moderator", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have the required permissions",
        )
    return current_user


async def get_current_admin(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserGroup.name).where(UserGroup.id == current_user.group_id)
    )
    group_name: str | None = result.scalar_one_or_none()
    if not group_name or group_name.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins only",
        )
    return current_user


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode = {"sub": subject, "exp": expire}
    return jwt.encode(
        to_encode, settings.SECRET_KEY_ACCESS, algorithm=settings.JWT_SIGNING_ALGORITHM
    )


def create_refresh_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"sub": str(user_id), "exp": expire}
    return jwt.encode(
        to_encode, settings.SECRET_KEY_REFRESH, algorithm=settings.JWT_SIGNING_ALGORITHM
    )


get_password_hash = hash_password
