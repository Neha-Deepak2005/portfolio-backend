import logging
import smtplib
from email.message import EmailMessage

from flask import current_app

log = logging.getLogger(__name__)


def send_email(subject, body, to=None, reply_to=None):
    """
    Send an email via SMTP. If SMTP is not configured the email is printed to
    the console instead, so the contact form still works in development.
    Returns True when an email was actually sent.
    """
    cfg = current_app.config
    to = to or cfg.get("MAIL_TO") or cfg.get("SMTP_USER")

    if not cfg.get("SMTP_HOST") or not to:
        print("\n" + "=" * 60)
        print(f"[EMAIL - console mode] To: {to or '(MAIL_TO not set)'}")
        print(f"Subject: {subject}")
        print("-" * 60)
        print(body)
        print("=" * 60 + "\n")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.get("MAIL_FROM") or cfg.get("SMTP_USER")
    msg["To"] = to
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(body)

    try:
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=15) as smtp:
            if cfg.get("SMTP_USE_TLS"):
                smtp.starttls()
            if cfg.get("SMTP_USER"):
                smtp.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
            smtp.send_message(msg)
        return True
    except Exception as exc:  # never break the contact form because of email
        log.warning("Email sending failed: %s", exc)
        return False
