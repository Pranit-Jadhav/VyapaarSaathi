"""Weekly summary scheduler for WhatsApp ledger users."""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from services.settings import get_settings
from services.voice_ledger import run_weekly_summary_job

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone=pytz.timezone("Asia/Kolkata"))


def start_scheduler() -> None:
    """Registers an optional weekly summary cron job."""
    settings = get_settings()
    if not settings.enable_weekly_summary:
        logger.info("Weekly summary scheduler disabled by environment flag.")
        return

    scheduler.add_job(
        run_weekly_summary_job,
        # Every Sunday at 7:00 PM IST
        CronTrigger(day_of_week="sun", hour=19, minute=0, timezone=pytz.timezone("Asia/Kolkata")),
        id="weekly_summary",
        replace_existing=True,
    )

    if not scheduler.running:
        scheduler.start()
    logger.info("Weekly summary scheduler started (Sunday 7:00 PM IST).")


def stop_scheduler() -> None:
    """Shuts down the background scheduler if running."""
    if scheduler.running:
        scheduler.shutdown()
