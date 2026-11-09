"""Persistent Alert Ledger for tracking multi-day high-risk pattern accumulation."""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings

logger = logging.getLogger(__name__)


class AlertLedger:
    """Manages persistent tracking of flagged individuals across calendar dates."""

    def __init__(self, ledger_path: Optional[str] = None):
        self.ledger_path = ledger_path or settings.ALERT_LEDGER_PATH
        os.makedirs(os.path.dirname(os.path.abspath(self.ledger_path)), exist_ok=True)

    def load(self) -> Dict[str, Any]:
        """Load ledger state from JSON file."""
        if not os.path.exists(self.ledger_path):
            return {}
        try:
            with open(self.ledger_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to load alert ledger from %s: %s", self.ledger_path, e)
            return {}

    def save(self, data: Dict[str, Any]) -> None:
        """Atomically persist ledger state to JSON file."""
        tmp_path = f"{self.ledger_path}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            # Atomic replace
            os.replace(tmp_path, self.ledger_path)
        except Exception as e:
            logger.error("Failed to save alert ledger to %s: %s", self.ledger_path, e)
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def record_daily_alerts(
        self,
        card_key: str,
        target_date: str,
        alerts: List[Dict[str, Any]],
        threshold: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Record daily alerts into ledger idempotently and return accounts breaching threshold.

        Returns a list of account dicts that have >= threshold alerts and need a cumulative report.
        """
        card = card_key.lower().strip()
        thresh = threshold if threshold is not None else settings.CUMULATIVE_ALERT_THRESHOLD
        ledger = self.load()
        breached_accounts: List[Dict[str, Any]] = []

        for alert in alerts:
            acct = str(alert.get("account_number", "")).strip()
            if not acct:
                continue

            ledger_key = f"{card}:{acct}"
            name = alert.get("individual_name", "")
            freq = alert.get("transaction_frequency", 0)
            usd = alert.get("total_usd_equivalent", 0.0)

            if ledger_key not in ledger:
                ledger[ledger_key] = {
                    "card_key": card,
                    "account_number": acct,
                    "individual_name": name,
                    "flagged_dates": [target_date],
                    "cumulative_alerts": 1,
                    "last_flagged_date": target_date,
                    "daily_history": [
                        {
                            "date": target_date,
                            "frequency": freq,
                            "total_usd_equivalent": usd,
                        }
                    ],
                    "cumulative_report_generated": False,
                    "cumulative_report_file": None,
                    "last_cumulative_report_date": None,
                }
            else:
                entry = ledger[ledger_key]
                if name and not entry.get("individual_name"):
                    entry["individual_name"] = name

                # Idempotency check: only append if date not already recorded
                if target_date not in entry["flagged_dates"]:
                    entry["flagged_dates"].append(target_date)
                    entry["flagged_dates"].sort()
                    entry["cumulative_alerts"] = len(entry["flagged_dates"])
                    entry["last_flagged_date"] = target_date
                    entry.setdefault("daily_history", []).append({
                        "date": target_date,
                        "frequency": freq,
                        "total_usd_equivalent": usd,
                    })

            entry = ledger[ledger_key]
            # Check if threshold is met/exceeded
            if entry["cumulative_alerts"] >= thresh:
                # If no report generated yet, or if flagged again since last report
                last_rep_date = entry.get("last_cumulative_report_date")
                if not entry.get("cumulative_report_generated") or last_rep_date != target_date:
                    breached_accounts.append(entry)

        self.save(ledger)
        return breached_accounts

    def mark_cumulative_report_generated(
        self,
        card_key: str,
        account_number: str,
        report_filename: str,
        target_date: str,
    ) -> None:
        """Mark that a cumulative report has been generated for this account."""
        card = card_key.lower().strip()
        acct = str(account_number).strip()
        ledger_key = f"{card}:{acct}"
        ledger = self.load()

        if ledger_key in ledger:
            ledger[ledger_key]["cumulative_report_generated"] = True
            ledger[ledger_key]["cumulative_report_file"] = report_filename
            ledger[ledger_key]["last_cumulative_report_date"] = target_date
            self.save(ledger)

    def get_ledger_summary(self) -> Dict[str, Any]:
        """Return high-level summary statistics of the alert ledger."""
        ledger = self.load()
        thresh = settings.CUMULATIVE_ALERT_THRESHOLD
        total_accounts = len(ledger)
        cumulative_breached = [
            e for e in ledger.values() if e.get("cumulative_alerts", 0) >= thresh
        ]

        # Sort accounts by cumulative_alerts descending
        sorted_accounts = sorted(
            ledger.values(),
            key=lambda x: (x.get("cumulative_alerts", 0), x.get("last_flagged_date", "")),
            reverse=True,
        )

        return {
            "total_tracked_accounts": total_accounts,
            "threshold": thresh,
            "cumulative_breached_count": len(cumulative_breached),
            "top_flagged_accounts": sorted_accounts[:20],
        }


# Singleton instance
alert_ledger = AlertLedger()

