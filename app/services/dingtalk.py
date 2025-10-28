import base64
import hashlib
import hmac
import time
import urllib.parse
import os
import requests
import logging

logger = logging.getLogger("weekreport.dingtalk")


def _gen_sign(secret: str, timestamp_ms: int) -> str:
    string_to_sign = f"{timestamp_ms}\n{secret}".encode("utf-8")
    h = hmac.new(secret.encode("utf-8"), string_to_sign, digestmod=hashlib.sha256).digest()
    return urllib.parse.quote_plus(base64.b64encode(h))


def send_reminder(text: str) -> bool:
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

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": "周报提醒",
            "text": f"**周报提醒**\n\n{text}\n\n请于今日18:00前完成。",
        }
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