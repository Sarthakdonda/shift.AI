"""Password-reset email delivery over SMTP; standard library only, no third-party sender."""
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from app.core.config import get_settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)
TIMEOUT = 20


def email_configured():
    s = get_settings()
    return bool(s.smtp_host.strip() and sender_address())


def sender_address():
    s = get_settings()
    return (s.smtp_from or s.smtp_username).strip()


def send_email(to, subject, body):
    """Deliver one plain-text message. Raises AppError with a safe message on failure."""
    s = get_settings()
    message = EmailMessage()
    message['From'] = formataddr((s.smtp_from_name.strip() or 'shift.AI', sender_address()))
    message['To'] = to
    message['Subject'] = subject
    message.set_content(body)
    try:
        if s.smtp_port == 465:
            with smtplib.SMTP_SSL(s.smtp_host.strip(), s.smtp_port, timeout=TIMEOUT, context=ssl.create_default_context()) as server:
                _deliver(server, message)
        else:
            with smtplib.SMTP(s.smtp_host.strip(), s.smtp_port, timeout=TIMEOUT) as server:
                if s.smtp_starttls:
                    server.starttls(context=ssl.create_default_context())
                _deliver(server, message)
    except (OSError, smtplib.SMTPException) as exc:
        logger.warning('Email delivery failed (%s)', type(exc).__name__)
        raise AppError('We could not send the email right now. Check the SMTP settings in backend/.env and try again.', 503, 'email_unavailable') from None


def _deliver(server, message):
    s = get_settings()
    if s.smtp_username and s.smtp_password:
        server.login(s.smtp_username.strip(), s.smtp_password)
    server.send_message(message)


def reset_email(name, link, minutes):
    subject = 'Reset your shift.AI password'
    body = (f'Hello {name},\n\n'
            'We received a request to choose a new password for your shift.AI workspace.\n'
            f'Open this link to continue:\n\n{link}\n\n'
            f'The link works once and expires in {minutes} minutes. '
            'If you did not ask for a new password, you can ignore this email and your current password stays active.\n\n'
            '— shift.AI\nClarity before complexity.\n')
    return subject, body
