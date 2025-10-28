import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr
import os
import logging


logger = logging.getLogger("weekreport.emailer")


def send_html_email(subject: str, html: str) -> bool:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "465"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    sender = os.getenv("MAIL_FROM", user or "noreply@example.com")
    to_list = [x.strip() for x in os.getenv("MAIL_TO", "").split(",") if x.strip()]
    use_tls_env = os.getenv("SMTP_USE_TLS", "").strip().lower()
    use_tls_flag = use_tls_env in ("1", "true", "yes")

    if not host or not user or not password or not to_list:
        logger.warning(
            "SMTP config incomplete: host=%s user_present=%s pass_present=%s to_count=%s",
            host,
            bool(user),
            bool(password),
            len(to_list),
        )
        return False

    # 网易邮箱等服务通常要求发件人地址与认证账户一致
    provider_host = (host or "").lower()
    if (
        user
        and sender
        and sender.lower() != user.lower()
        and (
            "smtp.163.com" in provider_host
            or "smtp.126.com" in provider_host
            or "smtp.yeah.net" in provider_host
        )
    ):
        logger.warning(
            "Adjust MAIL_FROM to match SMTP_USER for NetEase providers: from=%s -> %s",
            sender,
            user,
        )
        sender = user

    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr(("智能周报助手", sender))
    msg["To"] = ", ".join(to_list)

    # 选择协议：587 端口或显式开启 SMTP_USE_TLS → STARTTLS；否则默认 SSL
    try:
        if port == 587 or use_tls_flag:
            logger.warning("Using STARTTLS SMTP: host=%s port=%s", host, port)
            with smtplib.SMTP(host, port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(user, password)
                server.sendmail(sender, to_list, msg.as_string())
        else:
            logger.warning("Using SSL SMTP: host=%s port=%s", host, port)
            with smtplib.SMTP_SSL(host, port) as server:
                server.login(user, password)
                server.sendmail(sender, to_list, msg.as_string())
        logger.warning("SMTP send success: subject='%s' to_count=%s", subject, len(to_list))
        return True
    except Exception as e:
        logger.exception("SMTP send failed: %s", str(e))
        return False