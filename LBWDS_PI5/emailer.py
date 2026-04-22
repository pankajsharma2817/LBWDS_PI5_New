# emailer.py - send email alerts with image attachment
import os, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage

# Load credentials from environment variables (see .env.example)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; env vars can also be set externally

SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT   = int(os.environ.get("SMTP_PORT", 587))
EMAIL_USER  = os.environ.get("EMAIL_USER", "")
EMAIL_PASS  = os.environ.get("EMAIL_PASS", "")   # Gmail app password
EMAIL_TO    = os.environ.get("EMAIL_TO", "")

def send_email_alert(subject, body, img_path=None, recipient=EMAIL_TO):
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = recipient

    # attach body text
    msg.attach(MIMEText(body, "plain"))

    # attach image if provided
    if img_path and os.path.exists(img_path):
        with open(img_path, "rb") as f:
            msg.attach(MIMEImage(f.read(), name=os.path.basename(img_path)))

    # send email
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

    print(f"Email sent to {recipient} with subject '{subject}'")
