"""TMS-ATM Automated Report Generation and Cumulative Pattern Detection Engine.

Handles:
1. Daily transaction extraction and high-risk ATM rule processing.
2. Generating daily flagged transaction reports (Summary + Raw Unmodified Transactions).
3. Updating the persistent multi-day Alert Ledger (+1 alert per flagged day).
4. Generating Cumulative Investigation Reports (Entire transaction history for individuals >= threshold).
"""

from datetime import datetime, timedelta
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple
import zoneinfo
import openpyxl
import pandas as pd

from app.config import settings
from app.services.alert_ledger import AlertLedger, alert_ledger
from app.services.data_provider import TransactionDataProvider, get_data_provider
from app.services.s3_storage import s3_storage
from app.services.task1 import run_task1_tms_atm

logger = logging.getLogger(__name__)


class TMSReportEngine:
    """Core reporting engine for Task 1: TMS-ATM High-Risk Transaction Monitoring."""

    def __init__(
        self,
        data_provider: Optional[TransactionDataProvider] = None,
        ledger: Optional[AlertLedger] = None,
        day_output_dir: Optional[str] = None,
        cumulative_output_dir: Optional[str] = None,
    ):
        self.data_provider = data_provider or get_data_provider()
        self.ledger = ledger or alert_ledger
        self.day_output_dir = day_output_dir or settings.DAY_OUTPUT_DIR
        self.cumulative_output_dir = cumulative_output_dir or settings.CUMULATIVE_OUTPUT_DIR
        self.meta_path = os.path.join(self.day_output_dir, "daily_reports_meta.json")

        os.makedirs(self.day_output_dir, exist_ok=True)
        os.makedirs(self.cumulative_output_dir, exist_ok=True)

    def _load_metadata(self) -> Dict[str, Any]:
        """Load report metadata cache from disk."""
        if not os.path.exists(self.meta_path):
            return {}
        try:
            with open(self.meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Could not read report metadata cache: %s", e)
            return {}

    def _save_metadata(self, data: Dict[str, Any]) -> None:
        """Persist report metadata cache to disk atomically."""
        tmp_path = f"{self.meta_path}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.meta_path)
        except Exception as e:
            logger.warning("Could not save report metadata cache: %s", e)
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def get_report_metadata(self, filename: str) -> Dict[str, Any]:
        """Fetch metadata for a generated daily report with lazy inspection & caching."""
        meta = self._load_metadata()
        if filename in meta:
            return meta[filename]

        file_path = os.path.join(self.day_output_dir, filename)
        if not os.path.exists(file_path):
            return {
                "filename": filename,
                "card": "UNKNOWN",
                "date": "",
                "flagged_individuals_count": 0,
                "flagged_transactions_count": 0,
                "total_usd_volume": 0.0,
                "is_clean": True,
                "alerts": [],
                "size_bytes": 0,
                "generated_at": "",
            }

        # Inspect Excel file directly
        parts = filename[:-5].split("_")
        card = parts[2].upper() if len(parts) >= 4 else "UNKNOWN"
        dt = parts[3] if len(parts) >= 4 else ""
        stat = os.stat(file_path)

        alerts: List[Dict[str, Any]] = []
        flagged_tx_count = 0
        try:
            wb = openpyxl.load_workbook(file_path, read_only=True)
            if "Alerts Summary" in wb.sheetnames:
                sheet = wb["Alerts Summary"]
                rows = list(sheet.iter_rows(values_only=True))
                if len(rows) > 1:
                    headers = [str(h) for h in rows[0]]
                    for row in rows[1:]:
                        row_dict = dict(zip(headers, row))
                        alerts.append({
                            "account_number": str(row_dict.get("Account Number", "")),
                            "individual_name": str(row_dict.get("Individual Name", "")),
                            "alert_date": str(row_dict.get("Alert Date", dt)),
                            "transaction_frequency": int(row_dict.get("Transaction Frequency", 0) or 0),
                            "total_usd_equivalent": float(row_dict.get("Total USD Equivalent", 0.0) or 0.0),
                            "alert_count": int(row_dict.get("Alert Count (+1)", 1) or 1),
                        })
            if "Flagged Transactions" in wb.sheetnames:
                tx_sheet = wb["Flagged Transactions"]
                tx_rows = list(tx_sheet.iter_rows(values_only=True))
                flagged_tx_count = max(0, len(tx_rows) - 1)
            wb.close()
        except Exception as exc:
            logger.warning("Error inspecting report %s: %s", filename, exc)

        flagged_indiv_count = len(alerts)
        total_usd = sum(a.get("total_usd_equivalent", 0.0) for a in alerts)

        info = {
            "filename": filename,
            "card": card,
            "date": dt,
            "flagged_individuals_count": flagged_indiv_count,
            "flagged_transactions_count": flagged_tx_count,
            "total_usd_volume": round(total_usd, 2),
            "is_clean": flagged_indiv_count == 0,
            "alerts": alerts,
            "size_bytes": stat.st_size,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
        }
        meta[filename] = info
        self._save_metadata(meta)
        return info

    @staticmethod
    def get_yesterday_date(timezone_name: Optional[str] = None) -> str:
        """Compute yesterday's calendar date string (YYYY-MM-DD) in configured timezone."""
        if settings.SIMULATE_DATE:
            return settings.SIMULATE_DATE
        tz_name = timezone_name or settings.REPORT_TIMEZONE
        try:
            tz = zoneinfo.ZoneInfo(tz_name)
            now = datetime.now(tz)
        except Exception:
            now = datetime.now()
        yesterday = now - timedelta(days=1)
        return yesterday.strftime("%Y-%m-%d")

    def generate_daily_report(
        self,
        card_key: str,
        target_date: str,
        frequency_threshold: Optional[int] = None,
        usd_threshold: Optional[float] = None,
        cumulative_threshold: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Execute daily detection rule for a card provider and generate output reports."""
        card = card_key.lower().strip()
        freq_thresh = (
            frequency_threshold
            if frequency_threshold is not None
            else settings.FREQUENCY_THRESHOLD
        )
        usd_thresh = (
            usd_threshold if usd_threshold is not None else settings.USD_THRESHOLD
        )
        cum_thresh = (
            cumulative_threshold
            if cumulative_threshold is not None
            else settings.CUMULATIVE_ALERT_THRESHOLD
        )

        logger.info("Executing daily report for %s on %s...", card, target_date)
        df_daily = self.data_provider.get_daily_transactions(card, target_date)

        result = run_task1_tms_atm(
            df=df_daily,
            card_key=card,
            target_date=target_date,
            frequency_threshold=freq_thresh,
            usd_threshold=usd_thresh,
        )

        alerts = result.get("alerts", [])
        flagged_df = result.get("flagged_transactions", pd.DataFrame())
        flagged_count = result.get("flagged_individuals_count", 0)

        # 1. Generate Daily Excel Report
        daily_filename = f"daily_report_{card}_{target_date}.xlsx"
        daily_filepath = os.path.join(self.day_output_dir, daily_filename)

        with pd.ExcelWriter(daily_filepath, engine="openpyxl") as writer:
            # Sheet 1: Alert Summary
            if alerts:
                summary_df = pd.DataFrame(alerts)
                # Ensure friendly column headers
                col_rename = {
                    "account_number": "Account Number",
                    "individual_name": "Individual Name",
                    "alert_date": "Alert Date",
                    "transaction_frequency": "Transaction Frequency",
                    "total_usd_equivalent": "Total USD Equivalent",
                    "alert_count": "Alert Count (+1)",
                }
                summary_df = summary_df.rename(columns=col_rename)
            else:
                summary_df = pd.DataFrame(columns=[
                    "Account Number",
                    "Individual Name",
                    "Alert Date",
                    "Transaction Frequency",
                    "Total USD Equivalent",
                    "Alert Count (+1)",
                ])

            summary_df.to_excel(writer, sheet_name="Alerts Summary", index=False)

            # Sheet 2: Unmodified Flagged Transactions
            if len(flagged_df) > 0:
                flagged_df.to_excel(writer, sheet_name="Flagged Transactions", index=False)
            else:
                pd.DataFrame(columns=df_daily.columns).to_excel(
                    writer, sheet_name="Flagged Transactions", index=False
                )

        # 2. Update Alert Ledger
        breached_accounts = self.ledger.record_daily_alerts(
            card_key=card,
            target_date=target_date,
            alerts=alerts,
            threshold=cum_thresh,
        )

        # 3. Generate Cumulative Reports for any accounts hitting threshold
        cumulative_reports_created: List[Dict[str, Any]] = []
        for account_info in breached_accounts:
            acct = account_info["account_number"]
            cum_path, cum_file = self.generate_cumulative_report(
                card_key=card,
                account_number=acct,
                target_date=target_date,
                account_info=account_info,
            )
            cumulative_reports_created.append({
                "account_number": acct,
                "individual_name": account_info.get("individual_name", ""),
                "cumulative_alerts": account_info.get("cumulative_alerts", 0),
                "report_filename": cum_file,
                "report_filepath": cum_path,
            })

        # 4. Save metadata cache for fast status retrieval & UI preview
        stat = os.stat(daily_filepath)
        total_usd = sum(float(a.get("total_usd_equivalent", 0.0) or 0.0) for a in alerts)
        meta = self._load_metadata()
        meta[daily_filename] = {
            "filename": daily_filename,
            "card": card.upper(),
            "date": target_date,
            "flagged_individuals_count": flagged_count,
            "flagged_transactions_count": len(flagged_df),
            "total_usd_volume": round(total_usd, 2),
            "is_clean": flagged_count == 0,
            "alerts": alerts,
            "size_bytes": stat.st_size,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
        }
        self._save_metadata(meta)

        # 5. Cloud S3 Archival (if STORAGE_BACKEND="s3")
        s3_report_uri = None
        if s3_storage.is_enabled:
            s3_report_uri = s3_storage.upload_daily_report(
                local_path=daily_filepath,
                card=card,
                date_str=target_date,
                is_clean=(flagged_count == 0),
            )
            s3_storage.sync_ledger_to_s3(settings.ALERT_LEDGER_PATH)

        return {
            "card_key": card,
            "target_date": target_date,
            "total_transactions": len(df_daily),
            "total_atm_transactions": result.get("total_atm_transactions", 0),
            "flagged_individuals_count": flagged_count,
            "flagged_transactions_count": len(flagged_df),
            "total_usd_volume": round(total_usd, 2),
            "is_clean": flagged_count == 0,
            "daily_report_filename": daily_filename,
            "daily_report_filepath": daily_filepath,
            "s3_uri": s3_report_uri,
            "alerts": alerts,
            "cumulative_breached_count": len(cumulative_reports_created),
            "cumulative_reports": cumulative_reports_created,
        }

    def generate_cumulative_report(
        self,
        card_key: str,
        account_number: str,
        target_date: str,
        account_info: Optional[Dict[str, Any]] = None,
    ) -> (str, str):
        """Fetch entire transaction history and generate Cumulative Investigation Report."""
        card = card_key.lower().strip()
        acct = str(account_number).strip()

        logger.info("Generating cumulative report for %s account %s...", card, acct)
        df_history = self.data_provider.get_individual_history(card, acct)

        cum_filename = f"cumulative_{card}_{acct}_{target_date}.xlsx"
        cum_filepath = os.path.join(self.cumulative_output_dir, cum_filename)

        with pd.ExcelWriter(cum_filepath, engine="openpyxl") as writer:
            # Sheet 1: Dossier Summary
            info = account_info or {}
            flagged_dates_str = ", ".join(info.get("flagged_dates", [target_date]))
            meta_rows = [
                {"Field": "Card Provider", "Value": card.upper()},
                {"Field": "Account Number", "Value": acct},
                {"Field": "Individual Name", "Value": info.get("individual_name", "")},
                {"Field": "Cumulative Alert Count", "Value": info.get("cumulative_alerts", 0)},
                {"Field": "Cumulative Threshold", "Value": settings.CUMULATIVE_ALERT_THRESHOLD},
                {"Field": "All Flagged Dates", "Value": flagged_dates_str},
                {"Field": "Trigger Date", "Value": target_date},
                {"Field": "Total Historical Transactions on File", "Value": len(df_history)},
                {"Field": "Report Generated At", "Value": datetime.now().isoformat()},
            ]
            meta_df = pd.DataFrame(meta_rows)
            meta_df.to_excel(writer, sheet_name="Dossier Overview", index=False)

            # Daily Alert History Table
            history_rows = info.get("daily_history", [])
            if history_rows:
                pd.DataFrame(history_rows).to_excel(
                    writer, sheet_name="Alert Milestones", index=False
                )

            # Sheet 2: Entire Transaction History (Unmodified)
            if len(df_history) > 0:
                df_history.to_excel(writer, sheet_name="Full Transaction History", index=False)
            else:
                pd.DataFrame().to_excel(writer, sheet_name="Full Transaction History", index=False)

        # Mark in ledger
        self.ledger.mark_cumulative_report_generated(
            card_key=card,
            account_number=acct,
            report_filename=cum_filename,
            target_date=target_date,
        )

        # Upload cumulative report to S3 (if enabled)
        if s3_storage.is_enabled:
            s3_storage.upload_cumulative_report(cum_filepath, card, acct)

        return cum_filepath, cum_filename

    def get_report_details(self, filename: str) -> Dict[str, Any]:
        """Load report details including summary alerts and sample flagged transactions for UI preview."""
        safe_name = os.path.basename(filename)
        file_path = os.path.join(self.day_output_dir, safe_name)
        if not os.path.exists(file_path):
            return {"error": "Report not found", "filename": safe_name}

        meta = self.get_report_metadata(safe_name)
        tx_sample: List[Dict[str, Any]] = []
        try:
            wb = openpyxl.load_workbook(file_path, read_only=True)
            if "Flagged Transactions" in wb.sheetnames:
                sheet = wb["Flagged Transactions"]
                rows = list(sheet.iter_rows(values_only=True))
                if len(rows) > 1:
                    headers = [str(h) for h in rows[0]]
                    for row in rows[1:51]:
                        tx_sample.append({h: str(v) if v is not None else "" for h, v in zip(headers, row)})
            wb.close()
        except Exception as exc:
            logger.warning("Error reading transaction sample from %s: %s", safe_name, exc)

        return {
            "filename": safe_name,
            "card": meta.get("card", "UNKNOWN"),
            "date": meta.get("date", ""),
            "flagged_individuals_count": meta.get("flagged_individuals_count", 0),
            "flagged_transactions_count": meta.get("flagged_transactions_count", 0),
            "total_usd_volume": meta.get("total_usd_volume", 0.0),
            "is_clean": meta.get("is_clean", True),
            "alerts": meta.get("alerts", []),
            "transactions_sample": tx_sample,
            "size_bytes": meta.get("size_bytes", 0),
            "generated_at": meta.get("generated_at", ""),
        }

    def run_daily_batch(
        self,
        target_date: Optional[str] = None,
        cards: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Execute automated batch for yesterday or specified target date across all cards."""
        date_str = target_date or self.get_yesterday_date()
        target_cards = cards or ["visa", "pinelabs", "vegapay"]

        logger.info("=== Starting TMS-ATM Batch Run for Target Date: %s ===", date_str)
        t0 = datetime.now()

        card_results = {}
        total_flagged = 0
        total_cumulative = 0

        for card in target_cards:
            res = self.generate_daily_report(card_key=card, target_date=date_str)
            card_results[card] = res
            total_flagged += res.get("flagged_individuals_count", 0)
            total_cumulative += res.get("cumulative_breached_count", 0)

        t1 = datetime.now()
        duration_sec = (t1 - t0).total_seconds()

        logger.info(
            "=== Batch Run Completed in %.2fs: %d flagged individuals, %d cumulative dossiers ===",
            duration_sec,
            total_flagged,
            total_cumulative,
        )

        return {
            "status": "success",
            "target_date": date_str,
            "execution_timestamp": t1.isoformat(),
            "duration_seconds": round(duration_sec, 2),
            "total_flagged_individuals": total_flagged,
            "total_cumulative_reports": total_cumulative,
            "cards": card_results,
        }


# Singleton engine instance
report_engine = TMSReportEngine()

