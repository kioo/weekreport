from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta
import logging
from ..db import SessionLocal
from ..utils.summary import generate_weekly_summary
from .emailer import send_html_email
from .dingtalk import send_reminder

_scheduler = None
logger = logging.getLogger("weekreport.scheduler")


def _job_dingtalk_reminder():
    text = (
        "每周五 10:00 周报提醒：请大家按统一格式填写，\n"
        "直达链接：访问系统首页提交周报（例如 http://localhost:8000/）。"
    )
    logger.info("Trigger weekly DingTalk reminder job.")
    ok = send_reminder(text)
    logger.info("Weekly DingTalk reminder sent ok=%s", ok)


def _job_send_weekly_email():
    db = SessionLocal()
    try:
        html = generate_weekly_summary(db)
    finally:
        db.close()
    subject = f"团队周报汇总 - {datetime.now():%Y-%m-%d}"
    logger.warning("Trigger weekly email job subject=%s", subject)
    ok = send_html_email(subject, html)
    logger.warning("Weekly email sent ok=%s", ok)


def start_scheduler():
    global _scheduler
    if _scheduler:
        logger.info("Scheduler already started.")
        return
    _scheduler = BackgroundScheduler()
    # Friday 10:00 reminder
    _scheduler.add_job(_job_dingtalk_reminder, CronTrigger(day_of_week="fri", hour=10, minute=0))
    # Friday 18:00 weekly summary email
    _scheduler.add_job(_job_send_weekly_email, CronTrigger(day_of_week="fri", hour=18, minute=0))
    _scheduler.start()
    logger.info("Scheduler started. Weekly jobs registered.")


def schedule_dingtalk_once(text: str, delay_seconds: int = 0) -> dict:
    """
    添加一次性钉钉消息发送任务，默认立即发送；可设置延迟秒数。
    返回计划信息：是否成功、计划时间。
    """
    global _scheduler
    if not _scheduler:
        start_scheduler()
    try:
        delay_seconds = max(0, int(delay_seconds))
        run_time = datetime.now() + timedelta(seconds=delay_seconds)
        preview = (text or "").strip()
        if len(preview) > 80:
            preview = preview[:80] + "..."
        logger.info("Schedule one-off DingTalk. delay=%s run_at=%s text='%s'", delay_seconds, run_time.isoformat(), preview)
        _scheduler.add_job(
            send_reminder,
            DateTrigger(run_date=run_time),
            args=[text]
        )
        logger.info("One-off DingTalk scheduled at %s", run_time.isoformat())
        return {"scheduled": True, "run_at": run_time.isoformat(), "delay_seconds": delay_seconds}
    except Exception:
        logger.exception("Failed to schedule one-off DingTalk.")
        return {"scheduled": False, "run_at": None, "delay_seconds": delay_seconds}


def schedule_email_once(delay_seconds: int = 0) -> dict:
    """
    添加一次性周报汇总邮件发送任务，默认立即执行；可设置延迟秒数。
    返回计划信息：是否成功、计划时间。
    """
    global _scheduler
    if not _scheduler:
        start_scheduler()
    try:
        delay_seconds = max(0, int(delay_seconds))
        run_time = datetime.now() + timedelta(seconds=delay_seconds)
        logger.info(
            "Schedule one-off Weekly Email. delay=%s run_at=%s",
            delay_seconds,
            run_time.isoformat(),
        )
        _scheduler.add_job(
            _job_send_weekly_email,
            DateTrigger(run_date=run_time),
        )
        logger.info("One-off Weekly Email scheduled at %s", run_time.isoformat())
        return {"scheduled": True, "run_at": run_time.isoformat(), "delay_seconds": delay_seconds}
    except Exception:
        logger.exception("Failed to schedule one-off Weekly Email.")
        return {"scheduled": False, "run_at": None, "delay_seconds": delay_seconds}