"""CLI Entrypoint for TMS-ATM Automated Daily Report Generation.

Usage:
    # Run automated batch for yesterday (default for Linux Crontab):
    python -m app.report_runner --yesterday

    # Run for a specific date:
    python -m app.report_runner --date 2026-10-26

    # Backfill/simulate a date range:
    python -m app.report_runner --backfill-from 2026-10-20 --backfill-to 2026-10-26

    # Output structured JSON:
    python -m app.report_runner --yesterday --json
"""

import argparse
from datetime import datetime, timedelta
import json
import logging
import sys
from typing import List

from app.services.report_engine import report_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("app.report_runner")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CardLyze TMS-ATM Daily Report Generation and Alert Automation CLI."
    )
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument(
        "--yesterday",
        action="store_true",
        help="Run for yesterday's date in configured timezone (default).",
    )
    group.add_argument(
        "--date",
        type=str,
        help="Target date in ISO format YYYY-MM-DD.",
    )
    group.add_argument(
        "--backfill-from",
        type=str,
        help="Start date for backfill simulation (requires --backfill-to).",
    )

    parser.add_argument(
        "--backfill-to",
        type=str,
        help="End date for backfill simulation (inclusive).",
    )
    parser.add_argument(
        "--cards",
        nargs="+",
        default=["visa", "pinelabs", "vegapay"],
        help="List of card providers to run (default: visa pinelabs vegapay).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON summary to stdout.",
    )

    return parser.parse_args()


def run_backfill(start_date_str: str, end_date_str: str, cards: List[str]) -> List[dict]:
    """Sequentially execute daily batches from start_date to end_date."""
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")

    if start_dt > end_dt:
        raise ValueError(f"Start date {start_date_str} is after end date {end_date_str}")

    results = []
    curr = start_dt
    while curr <= end_dt:
        dt_str = curr.strftime("%Y-%m-%d")
        logger.info("--> Backfilling date: %s", dt_str)
        res = report_engine.run_daily_batch(target_date=dt_str, cards=cards)
        results.append(res)
        curr += timedelta(days=1)

    return results


def main() -> int:
    args = parse_args()

    try:
        if args.backfill_from:
            if not args.backfill_to:
                logger.error("--backfill-from requires --backfill-to")
                return 1
            batch_results = run_backfill(args.backfill_from, args.backfill_to, args.cards)
            output = {
                "status": "success",
                "mode": "backfill",
                "days_processed": len(batch_results),
                "runs": batch_results,
            }
        else:
            if args.date:
                target_date = args.date
            else:
                # Default: yesterday
                target_date = report_engine.get_yesterday_date()

            logger.info("Executing TMS-ATM daily batch for target date: %s", target_date)
            output = report_engine.run_daily_batch(target_date=target_date, cards=args.cards)

        if args.json:
            print(json.dumps(output, indent=2))
        else:
            print("\n================ BATCH EXECUTION SUMMARY ================")
            print(f"Target Date: {output.get('target_date', 'N/A')}")
            print(f"Status: {output.get('status', 'N/A')}")
            print(f"Total Flagged Individuals: {output.get('total_flagged_individuals', 0)}")
            print(f"Cumulative Reports Triggered: {output.get('total_cumulative_reports', 0)}")
            cards_summary = output.get("cards", {})
            for c_name, c_res in cards_summary.items():
                print(
                    f" - {c_name.upper()}: {c_res.get('flagged_individuals_count', 0)} flagged "
                    f"({c_res.get('cumulative_breached_count', 0)} cumulative reports) -> "
                    f"Report: {c_res.get('daily_report_filename')}"
                )
            print("=========================================================\n")

        return 0

    except Exception as e:
        logger.exception("Fatal error during batch execution: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())

