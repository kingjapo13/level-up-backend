import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL") or os.getenv("EMAIL_SENDER")


def send_email(to: str, subject: str, body: str):
    if SENDGRID_API_KEY:
        _send_via_sendgrid(to, subject, body)
    else:
        _send_via_smtp(to, subject, body)


def _send_via_sendgrid(to: str, subject: str, body: str):
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        message = Mail(
            from_email=SENDER_EMAIL,
            to_emails=to,
            subject=subject,
            html_content=body,
        )
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
        logger.info(f"Email sent via SendGrid to {to}")
    except Exception as e:
        logger.error(f"SendGrid email failed: {e}")
        raise


def _send_via_smtp(to: str, subject: str, body: str):
    try:
        password = os.getenv("EMAIL_PASSWORD")
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = to
        msg.attach(MIMEText(body, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, password)
            server.sendmail(SENDER_EMAIL, to, msg.as_string())
        logger.info(f"Email sent via SMTP to {to}")
    except Exception as e:
        logger.error(f"SMTP email failed: {e}")
        raise