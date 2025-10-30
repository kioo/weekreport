import base64
import hashlib
import hmac
import time
import urllib.parse
import os
import requests
import logging
from typing import Optional, List
import socket

logger = logging.getLogger("weekreport.dingtalk")


def _gen_sign(secret: str, timestamp_ms: int) -> str:
    string_to_sign = f"{timestamp_ms}\n{secret}".encode("utf-8")
    h = hmac.new(secret.encode("utf-8"), string_to_sign, digestmod=hashlib.sha256).digest()
    return urllib.parse.quote_plus(base64.b64encode(h))


def _infer_form_url() -> str:
    # 优先使用明确配置
    url = (
        os.getenv("REPORT_FORM_URL")
        or os.getenv("FORM_URL")
        or os.getenv("APP_BASE_URL")
        or None
    )
    if url:
        return url if url.endswith("/") else url + "/"

    # 尝试根据主机与端口自动推断
    host = (
        os.getenv("SERVER_HOST")
        or os.getenv("HOST")
        or None
    )
    if not host:
        try:
            host = socket.gethostbyname(socket.gethostname())
        except Exception:
            host = "127.0.0.1"
    port = os.getenv("PORT") or os.getenv("SERVER_PORT") or "8000"
    scheme = os.getenv("PUBLIC_SCHEME") or "http"
    return f"{scheme}://{host}:{port}/"


def send_reminder(text: str, at_mobiles: Optional[List[str]] = None) -> bool:
    webhook = os.getenv("DINGTALK_WEBHOOK")
    secret = os.getenv("DINGTALK_SECRET")
    if not webhook:
        logger.warning("DingTalk webhook not configured, skip send.")
        return False

    timestamp_ms = int(time.time() * 1000)
    params = {}
    if secret:
        sign = _gen_sign(secret, timestamp_ms)
        params = {"timestamp": str(timestamp_ms), "sign": sign}

    # 填写链接：优先配置，未配置时自动推断当前服务地址
    form_url = _infer_form_url()

    # 可选的 @ 配置：手机号或用户ID，以及是否 @ 全员
    env_at_mobiles = [m.strip() for m in (os.getenv("DINGTALK_AT_MOBILES", "").split(",")) if m.strip()]
    at_mobiles = at_mobiles if at_mobiles is not None and len(at_mobiles) > 0 else env_at_mobiles
    at_user_ids = [u.strip() for u in (os.getenv("DINGTALK_AT_USER_IDS", "").split(",")) if u.strip()]
    at_all = str(os.getenv("DINGTALK_AT_ALL", "false")).lower() in {"1", "true", "yes", "y"}

    # 在文本中加入 @ 提示（markdown 也支持），同时提供点击入口
    at_hint = ""
    if at_all:
        at_hint = "@所有人"
    elif at_mobiles:
        at_hint = " ".join([f"@{m}" for m in at_mobiles])

    markdown_text = (
        f"**周报提醒**\n\n{text}\n\n请于今日18:00前完成。\n\n"
        f"填写入口：[点击打开]({form_url})"
        + (f"\n\n{at_hint}" if at_hint else "")
    )

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": "周报提醒",
            "text": markdown_text,
        },
    }
    # DingTalk markdown 支持 at 字段
    if at_all or at_mobiles or at_user_ids:
        payload["at"] = {
            "isAtAll": at_all,
            **({"atMobiles": at_mobiles} if at_mobiles else {}),
            **({"atUserIds": at_user_ids} if at_user_ids else {}),
        }

    try:
        logger.warning("Sending DingTalk reminder. len(text)=%d", len(text))
        resp = requests.post(webhook, params=params, json=payload, timeout=10)
        ok = 200 <= resp.status_code < 300
        logger.warning("DingTalk response status=%s ok=%s", resp.status_code, ok)
        return ok
    except Exception:
        logger.exception("DingTalk send failed.")
        return False