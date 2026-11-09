"""Unit and integration tests for TMS-ATM Automated Reporting & Cumulative Engine."""

import os
import shutil
import tempfile
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.alert_ledger import AlertLedger
from app.services.data_provider import FileSimulationProvider
from app.services.report_engine import TMSReportEngine


@pytest.fixture
def temp_env():
    """Create a temporary directory structure for testing report generation."""
    temp_dir = tempfile.mkdtemp(prefix="cardlyze_test_")
    input_dir = os.path.join(temp_dir, "input_files")
    day_out_dir = os.path.join(temp_dir, "day_output")
    cum_out_dir = os.path.join(temp_dir, "cum_output")
    ledger_path = os.path.join(temp_dir, "alert_ledger.json")

    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(day_out_dir, exist_ok=True)
    os.makedirs(cum_out_dir, exist_ok=True)

    # Create synthetic daily files for visa on 3 dates
    # Target individual 'ACCT_999' will be flagged on all 3 days
    for dt in ["2026-10-01", "2026-10-02", "2026-10-03"]:
        rows = [
            # 4 ATM transactions of $500 each for ACCT_999 (Frequency 4 > 3, Total USD 2000 > 1500)
            {
                "spdate": dt.replace("-", "")[6:8] + dt.replace("-", "")[4:6] + dt.replace("-", "")[:4],
                "spacct": "ACCT_999",
                "spname": "TARGET USER",
                "spmcat": "6011",
                "spmusa": "500.0",
                "sptdes": "ATM CASH",
            }
            for _ in range(4)
        ]
        # Add a benign transaction
        rows.append({
            "spdate": dt.replace("-", "")[6:8] + dt.replace("-", "")[4:6] + dt.replace("-", "")[:4],
            "spacct": "ACCT_BENIGN",
            "spname": "SAFE USER",
            "spmcat": "5411",  # Groceries
            "spmusa": "50.0",
            "sptdes": "GROCERY STORE",
        })
        df = pd.DataFrame(rows)
        df.to_excel(os.path.join(input_dir, f"visa_{dt}.xlsx"), index=False)

    yield {
        "temp_dir": temp_dir,
        "input_dir": input_dir,
        "day_out_dir": day_out_dir,
        "cum_out_dir": cum_out_dir,
        "ledger_path": ledger_path,
    }

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_file_simulation_provider(temp_env):
    provider = FileSimulationProvider(
        input_files_dir=temp_env["input_dir"],
        monthly_files_dir=temp_env["temp_dir"],
    )
    df = provider.get_daily_transactions("visa", "2026-10-01")
    assert len(df) == 5
    assert "spacct" in df.columns

    dates = provider.get_available_dates("visa")
    assert dates == ["2026-10-03", "2026-10-02", "2026-10-01"]

    history = provider.get_individual_history("visa", "ACCT_999")
    # 4 rows on each of the 3 days = 12 total transactions
    assert len(history) == 12


def test_alert_ledger_idempotency_and_threshold(temp_env):
    ledger = AlertLedger(ledger_path=temp_env["ledger_path"])

    # Day 1: 1 alert
    alerts_day1 = [{
        "account_number": "ACCT_999",
        "individual_name": "TARGET USER",
        "transaction_frequency": 4,
        "total_usd_equivalent": 2000.0,
    }]
    breached = ledger.record_daily_alerts("visa", "2026-10-01", alerts_day1, threshold=3)
    assert len(breached) == 0

    state = ledger.load()
    assert state["visa:ACCT_999"]["cumulative_alerts"] == 1

    # Re-running Day 1 should NOT double-increment (Idempotent!)
    ledger.record_daily_alerts("visa", "2026-10-01", alerts_day1, threshold=3)
    state = ledger.load()
    assert state["visa:ACCT_999"]["cumulative_alerts"] == 1

    # Day 2: 2nd alert
    alerts_day2 = [{
        "account_number": "ACCT_999",
        "individual_name": "TARGET USER",
        "transaction_frequency": 4,
        "total_usd_equivalent": 2000.0,
    }]
    breached = ledger.record_daily_alerts("visa", "2026-10-02", alerts_day2, threshold=3)
    assert len(breached) == 0
    state = ledger.load()
    assert state["visa:ACCT_999"]["cumulative_alerts"] == 2

    # Day 3: 3rd alert -> THRESHOLD BREACHED!
    alerts_day3 = [{
        "account_number": "ACCT_999",
        "individual_name": "TARGET USER",
        "transaction_frequency": 4,
        "total_usd_equivalent": 2000.0,
    }]
    breached = ledger.record_daily_alerts("visa", "2026-10-03", alerts_day3, threshold=3)
    assert len(breached) == 1
    assert breached[0]["account_number"] == "ACCT_999"
    assert breached[0]["cumulative_alerts"] == 3


def test_report_engine_full_flow(temp_env):
    provider = FileSimulationProvider(
        input_files_dir=temp_env["input_dir"],
        monthly_files_dir=temp_env["temp_dir"],
    )
    ledger = AlertLedger(ledger_path=temp_env["ledger_path"])

    engine = TMSReportEngine(
        data_provider=provider,
        ledger=ledger,
        day_output_dir=temp_env["day_out_dir"],
        cumulative_output_dir=temp_env["cum_out_dir"],
    )

    # Run Day 1
    res1 = engine.generate_daily_report("visa", "2026-10-01", cumulative_threshold=3)
    assert res1["flagged_individuals_count"] == 1
    assert res1["cumulative_breached_count"] == 0
    assert os.path.exists(res1["daily_report_filepath"])

    # Run Day 2
    res2 = engine.generate_daily_report("visa", "2026-10-02", cumulative_threshold=3)
    assert res2["flagged_individuals_count"] == 1
    assert res2["cumulative_breached_count"] == 0

    # Run Day 3 -> Triggers cumulative dossier!
    res3 = engine.generate_daily_report("visa", "2026-10-03", cumulative_threshold=3)
    assert res3["flagged_individuals_count"] == 1
    assert res3["cumulative_breached_count"] == 1

    cum_report = res3["cumulative_reports"][0]
    assert cum_report["account_number"] == "ACCT_999"
    assert os.path.exists(cum_report["report_filepath"])

    # Verify cumulative excel workbook has all 3 sheets
    xl = pd.ExcelFile(cum_report["report_filepath"])
    assert "Dossier Overview" in xl.sheet_names
    assert "Alert Milestones" in xl.sheet_names
    assert "Full Transaction History" in xl.sheet_names

    history_sheet = xl.parse("Full Transaction History")
    # All 12 historical transactions must be present
    assert len(history_sheet) == 12


def test_api_automated_endpoints():
    client = TestClient(app)

    # 1. Overview
    resp = client.get("/api/task1/automated/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "yesterday_date" in data
    assert "ledger_summary" in data

    # 2. Ledger endpoint
    resp_ledger = client.get("/api/task1/automated/ledger")
    assert resp_ledger.status_code == 200
    assert isinstance(resp_ledger.json(), dict)
