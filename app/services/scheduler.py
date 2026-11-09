"""Background Scheduler and Startup Catch-up Service for CardLyze TMS-ATM.

Schedules daily execution at configured midnight delay (e.g. 12:15 AM IST)
and performs catch-up checks on server boot if past daily runs were missed.
"""

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Optional
import zoneinfo

from app.config import settings
from app.services.report_engine import report_engine

logger = logging.getLogger(__name__)


class ReportScheduler:
    """Manages scheduled daily execution and startup catch-up."""

    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._running: bool = False

    def get_seconds_until_next_run(self) -> float:
        """Calculate seconds until the next scheduled daily execution (e.g. 00:15 in REPORT_TIMEZONE)."""
        try:
            tz = zoneinfo.ZoneInfo(settings.REPORT_TIMEZONE)
            now = datetime.now(tz)
        except Exception:
            now = datetime.now()

        delay_minutes = settings.DAILY_RUN_DELAY_MINUTES

        # Target today at 00:delay_minutes
        target = now.replace(hour=0, minute=delay_minutes, second=0, microsecond=0)
        if now >= target:
            # If already past today's run time, schedule for tomorrow at 00:delay_minutes
            target += timedelta(days=1)

        delta = (target - now).total_seconds()
        logger.info(
            "Next scheduled TMS-ATM report run at %s (%s) in %.1f seconds",
            target.strftime("%Y-%m-%d %H:%M:%S"),
            settings.REPORT_TIMEZONE,
            delta,
        )
        return max(1.0, delta)

    async def _scheduler_loop(self):
        """Continuous background loop waiting until scheduled midnight delay."""
        logger.info("TMS-ATM Automated Report Scheduler started.")
        while self._running:
            try:
                sleep_seconds = self.get_seconds_until_next_run()
                await asyncio.sleep(sleep_seconds)

                if not self._running:
                    break

                logger.info("Scheduled execution trigger fired! Running daily TMS batch...")
                # Run batch in thread pool to prevent blocking async event loop
                await asyncio.to_thread(report_engine.run_daily_batch)

            except asyncio.CancelledError:
                logger.info("Scheduler task cancelled.")
                break
            except Exception as e:
                logger.error("Error in scheduler loop: %s. Retrying in 60s.", e)
                await asyncio.sleep(60.0)

    def check_and_run_startup_catchup(self):
        """Check if yesterday's report exists; if missing, run catch-up immediately."""
        if not settings.STARTUP_CATCHUP_ENABLED:
            return

        yesterday = report_engine.get_yesterday_date()
        logger.info("Checking startup catch-up status for target date: %s", yesterday)

        import os
        # Check if at least one daily report for yesterday exists
        day_dir = settings.DAY_OUTPUT_DIR
        cards = ["visa", "pinelabs", "vegapay"]
        missing_cards = []

        for card in cards:
            fname = f"daily_report_{card}_{yesterday}.xlsx"
            fpath = os.path.join(day_dir, fname)
            if not os.path.exists(fpath):
                missing_cards.append(card)

        if missing_cards:
            logger.info(
                "Startup catch-up: Reports missing for %s on %s. Triggering backfill...",
                missing_cards,
                yesterday,
            )
            report_engine.run_daily_batch(target_date=yesterday, cards=missing_cards)
        else:
            logger.info("Startup catch-up: All daily reports for %s are up to date.", yesterday)

    def start(self):
        """Start the background scheduler."""
        if not settings.AUTO_SCHEDULER_ENABLED:
            logger.info("Automated Report Scheduler is disabled via configuration.")
            return

        self._running = True
        loop = asyncio.get_event_loop()

        # Run startup catch-up check non-blockingly
        loop.run_in_executor(None, self.check_and_run_startup_catchup)

        # Start recurring timer loop
        self._task = asyncio.create_task(self._scheduler_loop())

    def stop(self):
        """Stop the background scheduler."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("TMS-ATM Automated Report Scheduler stopped.")


report_scheduler = ReportScheduler()

