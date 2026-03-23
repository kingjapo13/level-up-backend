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
        def send_trial_expiry_warning(to: str, username: str, days_left: int):
    subject = f"⏰ Your LevelUp trial expires in {days_left} day{'s' if days_left != 1 else ''}!"
    body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #0a0a0a; color: white; padding: 40px; border-radius: 16px;">
        <h1 style="color: #00FF88; text-align: center;">LevelUp 🏆</h1>
        <h2 style="text-align: center;">Your free trial expires in {days_left} day{'s' if days_left != 1 else ''}!</h2>
        <p style="color: #888; text-align: center;">Hey {username}, don't lose access to your AI coaching.</p>

        <div style="background: #111; border-radius: 12px; padding: 24px; margin: 24px 0; border: 1px solid #222;">
            <h3 style="color: #00FF88;">What you'll lose when trial ends:</h3>
            <p>❌ Unlimited video uploads</p>
            <p>❌ AI coaching feedback</p>
            <p>❌ Weekly performance reports</p>
            <p>❌ Progress tracking</p>
        </div>

        <div style="text-align: center; margin: 32px 0;">
            <a href="https://levelupai.com" style="background: #00FF88; color: #000; padding: 16px 32px; border-radius: 12px; text-decoration: none; font-weight: bold; font-size: 18px;">
                Upgrade Now — From $20/mo
            </a>
        </div>

        <p style="color: #555; text-align: center; font-size: 12px;">
            No credit card was required for your trial. Upgrade anytime to keep training.
        </p>
    </div>
    """
    send_email(to=to, subject=subject, body=body)


def send_trial_expired(to: str, username: str):
    subject = "⚠️ Your LevelUp trial has ended"
    body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #0a0a0a; color: white; padding: 40px; border-radius: 16px;">
        <h1 style="color: #00FF88; text-align: center;">LevelUp 🏆</h1>
        <h2 style="text-align: center; color: #FF4444;">Your free trial has ended</h2>
        <p style="color: #888; text-align: center;">Hey {username}, your 7-day free trial is over.</p>

        <div style="background: #111; border-radius: 12px; padding: 24px; margin: 24px 0; border: 1px solid #FF4444;">
            <h3 style="color: white;">Your progress is waiting for you</h3>
            <p style="color: #888;">You analyzed {'{sessions}'} videos during your trial. Keep the momentum going!</p>
        </div>

        <div style="background: #111; border-radius: 12px; padding: 24px; margin: 24px 0; border: 1px solid #222;">
            <h3 style="color: #00FF88;">Pro Plan — $20/month</h3>
            <p>✅ Unlimited video uploads</p>
            <p>✅ Full AI coaching feedback</p>
            <p>✅ Weekly reports</p>
            <br/>
            <h3 style="color: #00FF88;">Elite Plan — $40/month</h3>
            <p>✅ Everything in Pro</p>
            <p>✅ Advanced biomechanics</p>
            <p>✅ Personal training plans</p>
        </div>

        <div style="text-align: center; margin: 32px 0;">
            <a href="https://levelupai.com" style="background: #00FF88; color: #000; padding: 16px 32px; border-radius: 12px; text-decoration: none; font-weight: bold; font-size: 18px;">
                Upgrade and Keep Training
            </a>
        </div>
    </div>
    """
    send_email(to=to, subject=subject, body=body)