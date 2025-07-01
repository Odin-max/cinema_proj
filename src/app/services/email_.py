import smtplib
from email.message import EmailMessage
from app.core.config import settings


async def send_activation_email(to_email: str, token: str) -> None:
    link = f"{settings.BACKEND_URL}/auth/activate?token={token}"
    msg = EmailMessage()
    msg["Subject"] = "Activate your account"
    msg["From"] = settings.EMAIL_HOST_USER
    msg["To"] = to_email
    msg.set_content(
        f"Welcome! Click here to activate your account:\n\n{link}\n\n(This link expires in 24h.)"
    )

    with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as smtp:
        if settings.EMAIL_USE_TLS:
            smtp.starttls()
        smtp.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        smtp.send_message(msg)


async def send_password_reset_email(to_email: str, token: str) -> None:
    link = f"{settings.BACKEND_URL}/auth/password/reset?token={token}"
    msg = EmailMessage()
    msg["Subject"] = "Reset your password"
    msg["From"] = settings.EMAIL_HOST_USER
    msg["To"] = to_email
    msg.set_content(
        f"You requested a password reset. Click here to choose a new password:\n\n{link}\n\n(This link expires in 24h.)"
    )

    with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as smtp:
        if settings.EMAIL_USE_TLS:
            smtp.starttls()
        smtp.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        smtp.send_message(msg)
