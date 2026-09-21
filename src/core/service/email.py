import asyncio
import logging
import smtplib
import ssl
from email.mime.text import MIMEText

from src.config import cfg

logger = logging.getLogger(__name__)


def _send_sync(to_email: str, subject: str, html_body: str) -> None:
    message = MIMEText(html_body, "html", "utf-8")
    message["Subject"] = subject
    message["From"] = cfg.email.smtp_from or cfg.email.smtp_user
    message["To"] = to_email

    context = ssl.create_default_context()
    if cfg.email.smtp_use_ssl:
        with smtplib.SMTP_SSL(
            cfg.email.smtp_host, cfg.email.smtp_port, context=context, timeout=15
        ) as server:
            server.login(cfg.email.smtp_user, cfg.email.smtp_password)
            server.sendmail(message["From"], [to_email], message.as_string())
    else:
        with smtplib.SMTP(cfg.email.smtp_host, cfg.email.smtp_port, timeout=15) as server:
            server.starttls(context=context)
            server.login(cfg.email.smtp_user, cfg.email.smtp_password)
            server.sendmail(message["From"], [to_email], message.as_string())


async def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Отправляет письмо через SMTP. Не бросает исключение наружу —
    сбой почты не должен ронять регистрацию/создание инвайта."""
    if not cfg.email.is_configured:
        logger.warning(
            "SMTP не настроен (EMAIL_SMTP_*), письмо на %s не отправлено: %s",
            to_email,
            subject,
        )
        return False
    try:
        await asyncio.to_thread(_send_sync, to_email, subject, html_body)
        return True
    except Exception:
        logger.exception("Не удалось отправить письмо на %s", to_email)
        return False


async def send_verification_email(to_email: str, first_name: str, token: str) -> bool:
    link = f"{cfg.email.frontend_base_url}/verify-email?token={token}"
    html = f"""
    <p>Здравствуйте, {first_name}!</p>
    <p>Подтвердите почту, чтобы начать пользоваться платформой МЕТРИКА:</p>
    <p><a href="{link}">{link}</a></p>
    <p>Ссылка действует {cfg.email.verification_ttl_hours} ч.</p>
    """
    return await send_email(to_email, "Подтверждение почты — МЕТРИКА", html)


async def send_invite_email(
    to_email: str, tutor_name: str, role_label: str, token: str
) -> bool:
    link = f"{cfg.email.frontend_base_url}/register/invite/{token}"
    html = f"""
    <p>Здравствуйте!</p>
    <p>{tutor_name} приглашает вас на платформу МЕТРИКА как «{role_label}».</p>
    <p>Перейдите по ссылке, чтобы зарегистрироваться:</p>
    <p><a href="{link}">{link}</a></p>
    <p>Ссылка действует {cfg.email.invite_ttl_days} дн. и одноразовая.</p>
    """
    return await send_email(to_email, "Приглашение на платформу МЕТРИКА", html)
