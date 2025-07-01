import uuid
from datetime import datetime, timedelta

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import (
    create_access_token,
    get_current_user,
    get_password_hash,
    hash_password,
    settings,
    verify_password,
)
from app.db.session import get_db
from app.models.user_models import (
    ActivationToken,
    PasswordResetToken,
    RefreshToken,
    User,
)
from app.schemas.auth_schema import (
    ActivationSchema,
    EmailSchema,
    TokenRefreshSchema,
    TokenSchema,
    UserCreate,
    UserRead,
)
from app.services.email_ import send_activation_email, send_password_reset_email


router = APIRouter(prefix="", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    data: UserCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    exists = await db.scalar(select(User).where(User.email == data.email))
    if exists:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    user = User(
        email=data.email,
        hashed_password=get_password_hash(data.password),
        is_active=False,
        group_id=settings.DEFAULT_GROUP_ID,
    )
    db.add(user)
    await db.flush()

    token_str = str(uuid.uuid4())
    activation = ActivationToken(
        user_id=user.id,
        token=token_str,
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.add(activation)
    await db.commit()

    background_tasks.add_task(send_activation_email, user.email, token_str)
    return {"message": "User registered. Activation email sent."}


@router.api_route(
    "/activate",
    methods=["GET", "POST"],
    status_code=status.HTTP_200_OK,
)
async def activate(
    token: str | None = Query(None),
    data: ActivationSchema | None = Body(None),
    db: AsyncSession = Depends(get_db),
):
    tok = token or (data and data.token)
    if not tok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Token is required")

    stmt = (
        select(ActivationToken)
        .options(selectinload(ActivationToken.user))
        .where(ActivationToken.token == tok)
    )
    result = await db.execute(stmt)
    db_token: ActivationToken | None = result.scalar_one_or_none()

    if not db_token or db_token.expires_at < datetime.utcnow():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired token")

    user = db_token.user
    user.is_active = True

    await db.delete(db_token)
    await db.commit()

    return {"message": "Account activated successfully."}


@router.get("/me", response_model=UserRead, status_code=status.HTTP_200_OK)
async def read_current_user(current_user=Depends(get_current_user)):
    return current_user


@router.post("/resend-activation", status_code=status.HTTP_200_OK)
async def resend_activation(
    data: EmailSchema,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    user = await db.scalar(select(User).where(User.email == data.email))
    if not user or user.is_active:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="User not found or already active"
        )

    result = await db.execute(
        select(ActivationToken).where(ActivationToken.user_id == user.id)
    )
    old_tokens = result.scalars().all()

    for tok in old_tokens:
        await db.delete(tok)

    await db.flush()

    new_token = str(uuid.uuid4())
    activation = ActivationToken(
        user_id=user.id,
        token=new_token,
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.add(activation)

    await db.commit()

    background_tasks.add_task(send_activation_email, user.email, new_token)

    return {"message": "A new activation email has been sent."}


@router.post("/login", response_model=TokenSchema)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    user = await db.scalar(select(User).where(User.email == form_data.username))
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Account not activated")

    access_token = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    refresh_token_str = str(uuid.uuid4())
    expires = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    refresh = RefreshToken(user_id=user.id, token=refresh_token_str, expires_at=expires)

    db.add(refresh)
    await db.commit()

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=False,
        samesite="lax",
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_str,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=TokenSchema)
async def refresh_token(
    data: TokenRefreshSchema,
    db: AsyncSession = Depends(get_db),
):
    rt = await db.scalar(
        select(RefreshToken).where(RefreshToken.token == data.refresh_token)
    )
    if not rt or rt.expires_at < datetime.utcnow():
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token"
        )

    access_token = create_access_token(subject=str(rt.user_id))
    return {
        "access_token": access_token,
        "refresh_token": data.refresh_token,
        "token_type": "bearer",
    }


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(data: TokenRefreshSchema, db: AsyncSession = Depends(get_db)):
    rt = await db.scalar(
        select(RefreshToken).where(RefreshToken.token == data.refresh_token)
    )
    if rt:
        await db.delete(rt)
        await db.commit()
    return {"message": "Logged out successfully"}


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    data: EmailSchema,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    user = await db.scalar(select(User).where(User.email == data.email))
    if not user or not user.is_active:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="User not found or not active"
        )

    await db.execute(
        delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    )
    token_str = str(uuid.uuid4())
    reset = PasswordResetToken(
        user_id=user.id,
        token=token_str,
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.add(reset)
    await db.commit()

    background_tasks.add_task(send_password_reset_email, user.email, token_str)
    return {"message": "Password reset email sent."}


@router.get("/password/reset", response_class=HTMLResponse)
async def password_reset_form(
    request: Request, token: str, db: AsyncSession = Depends(get_db)
):
    db_token = await db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token == token)
    )
    if not db_token or db_token.expires_at < datetime.utcnow():
        raise HTTPException(400, "Invalid or expired token")
    html = f"""
    <html>
      <head><title>Reset password</title></head>
      <body>
        <h1>Reset your password</h1>
        <form action="/auth/password/reset" method="post">
          <input type="hidden" name="token" value="{token}" />
          <label>New password: <input type="password" name="new_password" /></label>
          <button type="submit">Submit</button>
        </form>
      </body>
    </html>
    """
    return HTMLResponse(html)


@router.post(
    "/password/reset", status_code=status.HTTP_200_OK, response_class=JSONResponse
)
async def password_reset_submit(
    token: str = Form(...),
    new_password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PasswordResetToken)
        .options(selectinload(PasswordResetToken.user))
        .where(PasswordResetToken.token == token)
    )
    db_token = result.scalar_one_or_none()
    if not db_token or db_token.expires_at < datetime.utcnow():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token"
        )

    user = db_token.user
    user.hashed_password = hash_password(new_password)

    await db.execute(
        delete(PasswordResetToken).where(PasswordResetToken.id == db_token.id)
    )
    await db.commit()

    return {"message": "Password has been reset successfully."}
