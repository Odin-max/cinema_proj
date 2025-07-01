from datetime import datetime
from celery import shared_task
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.user_models import ActivationToken, PasswordResetToken, RefreshToken

engine = create_engine(str(settings.DATABASE_URL).replace('+asyncpg', '+pg8000'))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@shared_task
def remove_expired_tokens():
    now = datetime.utcnow()
    db = SessionLocal()
    try:
        db.execute(
            delete(ActivationToken).
            where(ActivationToken.expires_at < now)
        )
        db.execute(
            delete(PasswordResetToken).
            where(PasswordResetToken.expires_at < now)
        )
        db.execute(
            delete(RefreshToken).
            where(RefreshToken.expires_at < now)
        )
        db.commit()
    finally:
        db.close()
