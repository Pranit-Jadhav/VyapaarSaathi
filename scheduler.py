"""Weekly summary scheduler for WhatsApp ledger users."""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import pytz

from services.settings import get_settings
from services.voice_ledger import run_instant_stock_alert_job, run_weekly_summary_job

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone=pytz.timezone("Asia/Kolkata"))


def start_scheduler() -> None:
    """Registers optional scheduler jobs (weekly summary + instant stock alerts)."""
    settings = get_settings()
    jobs_added = False

    if settings.enable_weekly_summary:
        scheduler.add_job(
            run_weekly_summary_job,
            # Every Sunday at 7:00 PM IST
            CronTrigger(day_of_week="sun", hour=19, minute=0, timezone=pytz.timezone("Asia/Kolkata")),
            id="weekly_summary",
            replace_existing=True,
        )
        jobs_added = True
        logger.info("Weekly summary scheduler enabled (Sunday 7:00 PM IST).")
    else:
        logger.info("Weekly summary scheduler disabled by environment flag.")

    if settings.enable_instant_stock_alerts:
        scheduler.add_job(
            run_instant_stock_alert_job,
            IntervalTrigger(seconds=settings.instant_stock_alert_interval_seconds),
            id="instant_stock_alert",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        jobs_added = True
        logger.info(
            "Instant stock alert scheduler enabled (every %ss, threshold=%s units).",
            settings.instant_stock_alert_interval_seconds,
            settings.instant_stock_alert_units_threshold,
        )
    else:
        logger.info("Instant stock alert scheduler disabled by environment flag.")

    if jobs_added and not scheduler.running:
        scheduler.start()
    if not jobs_added:
        logger.info("No scheduler jobs enabled.")


def stop_scheduler() -> None:
    """Shuts down the background scheduler if running."""
    if scheduler.running:
        scheduler.shutdown()
