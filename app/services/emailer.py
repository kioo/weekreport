import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr
import os


def send_html_email(subject: str, html: str) -> bool:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "465"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    sender = os.getenv("MAIL_FROM", user or "noreply@example.com")
    to_list = [x.strip() for x in os.getenv("MAIL_TO", "").split(",") if x.strip()]

    if not host or not user or not password or not to_list:
        return False

    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr(("智能周报助手", sender))
    msg["To"] = ", ".join(to_list)

    try:
        with smtplib.SMTP_SSL(host, port) as server:
            server.login(user, password)
            server.sendmail(sender, to_list, msg.as_string())
        return True
    except Exception:
        return False