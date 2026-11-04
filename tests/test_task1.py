"""Comprehensive Pytest Suite for Task 1: TMS-ATM High-Risk Transaction Monitoring."""

import io
import pytest
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.services.task1 import (
    ATM_HIGH_RISK_MCCS,
    get_available_dates,
    normalize_date_series,
    run_task1_tms_atm,
)
from app.store import session_store


@pytest.fixture(autouse=True)
def clean_sessions():
    """Wipe session store before and after each test."""
    session_store.sweep_expired()
    with session_store._lock:
        for s in list(session_store._sessions.values()):
            s.wipe()
        session_store._sessions.clear()
    yield
    with session_store._lock:
        for s in list(session_store._sessions.values()):
            s.wipe()
        session_store._sessions.clear()


@pytest.fixture
def client():
    return TestClient(app)


# --- UNIT TESTS FOR SERVICE LOGIC ---

def test_atm_high_risk_mcc_constant():
    assert "6011" in ATM_HIGH_RISK_MCCS
    assert "6010" in ATM_HIGH_RISK_MCCS
    assert "6050" in ATM_HIGH_RISK_MCCS
    assert "6051" in ATM_HIGH_RISK_MCCS
    assert "5812" not in ATM_HIGH_RISK_MCCS


def test_visa_task1_detection_logic():
    # 5 ATM txns for Acct1 ($2000 total) -> Should alert
    # 2 ATM txns for Acct2 ($2000 total) -> Frequency <= 3, should NOT alert
    # 4 ATM txns for Acct3 ($1000 total) -> Amount <= 1500, should NOT alert
    # 4 Retail txns (MCC 5812) for Acct4 -> Not ATM, should NOT alert
    rows = [
        # Acct1: 4 txns on 2026-09-30, 1 on 2026-09-29
        {"spbusd": "2026-09-30", "spdate": "30092026", "spacct": "P001", "spname": "User One", "spmcat": "6011", "spmusa": 600.0, "source_file": "f1"},
        {"spbusd": "2026-09-30", "spdate": "30092026", "spacct": "P001", "spname": "User One", "spmcat": "6011", "spmusa": 600.0, "source_file": "f1"},
        {"spbusd": "2026-09-30", "spdate": "30092026", "spacct": "P001", "spname": "User One", "spmcat": "6010", "spmusa": 500.0, "source_file": "f1"},
        {"spbusd": "2026-09-30", "spdate": "30092026", "spacct": "P001", "spname": "User One", "spmcat": "6051", "spmusa": 400.0, "source_file": "f1"},
        {"spbusd": "2026-09-29", "spdate": "29092026", "spacct": "P001", "spname": "User One", "spmcat": "6011", "spmusa": 800.0, "source_file": "f1"},

        # Acct2: 2 txns on 2026-09-30 ($2000 total)
        {"spbusd": "2026-09-30", "spdate": "30092026", "spacct": "P002", "spname": "User Two", "spmcat": "6011", "spmusa": 1000.0, "source_file": "f1"},
        {"spbusd": "2026-09-30", "spdate": "30092026", "spacct": "P002", "spname": "User Two", "spmcat": "6011", "spmusa": 1000.0, "source_file": "f1"},

        # Acct3: 4 txns on 2026-09-30 ($800 total)
        {"spbusd": "2026-09-30", "spdate": "30092026", "spacct": "P003", "spname": "User Three", "spmcat": "6011", "spmusa": 200.0, "source_file": "f1"},
        {"spbusd": "2026-09-30", "spdate": "30092026", "spacct": "P003", "spname": "User Three", "spmcat": "6011", "spmusa": 200.0, "source_file": "f1"},
        {"spbusd": "2026-09-30", "spdate": "30092026", "spacct": "P003", "spname": "User Three", "spmcat": "6011", "spmusa": 200.0, "source_file": "f1"},
        {"spbusd": "2026-09-30", "spdate": "30092026", "spacct": "P003", "spname": "User Three", "spmcat": "6011", "spmusa": 200.0, "source_file": "f1"},

        # Acct4: Non-ATM MCC 5812
        {"spbusd": "2026-09-30", "spdate": "30092026", "spacct": "P004", "spname": "User Four", "spmcat": "5812", "spmusa": 2000.0, "source_file": "f1"},
        {"spbusd": "2026-09-30", "spdate": "30092026", "spacct": "P004", "spname": "User Four", "spmcat": "5812", "spmusa": 2000.0, "source_file": "f1"},
        {"spbusd": "2026-09-30", "spdate": "30092026", "spacct": "P004", "spname": "User Four", "spmcat": "5812", "spmusa": 2000.0, "source_file": "f1"},
        {"spbusd": "2026-09-30", "spdate": "30092026", "spacct": "P004", "spname": "User Four", "spmcat": "5812", "spmusa": 2000.0, "source_file": "f1"},
    ]
    df = pd.DataFrame(rows)

    res = run_task1_tms_atm(df, "visa", "2026-09-30")
    assert res["target_date"] == "2026-09-30"
    assert res["total_atm_transactions"] == 10  # 4 from Acct1, 2 from Acct2, 4 from Acct3
    assert res["flagged_individuals_count"] == 1
    
    alert = res["alerts"][0]
    assert alert["account_number"] == "P001"
    assert alert["individual_name"] == "User One"
    assert alert["transaction_frequency"] == 4
    assert alert["total_usd_equivalent"] == 2100.0
    assert alert["alert_count"] == 1

    # Exact column retention with zero column modification
    flagged_df = res["flagged_transactions"]
    assert len(flagged_df) == 4
    assert list(flagged_df.columns) == list(df.columns)
    assert set(flagged_df["spacct"]) == {"P001"}


def test_pinelabs_task1_detection_logic():
    # PineLabs uses "Wallet Number", "mcc" with hyphen prefix, and "Billing Amount"
    rows = [
        {"Value Date": "28/09/2026 00:00:00", "Wallet Number": "W100", "Device Number": "5417XXXX1111", "mcc": "6011-Member ATM Cash", "Billing Amount": 500.0},
        {"Value Date": "28/09/2026 00:00:00", "Wallet Number": "W100", "Device Number": "5417XXXX1111", "mcc": "6011-Member ATM Cash", "Billing Amount": 500.0},
        {"Value Date": "28/09/2026 00:00:00", "Wallet Number": "W100", "Device Number": "5417XXXX1111", "mcc": "6011-Member ATM Cash", "Billing Amount": 600.0},
        {"Value Date": "28/09/2026 00:00:00", "Wallet Number": "W100", "Device Number": "5417XXXX1111", "mcc": "6010-Manual Cash", "Billing Amount": 100.0},
        
        # Another wallet: 4 txns, but only $400 total
        {"Value Date": "28/09/2026 00:00:00", "Wallet Number": "W200", "Device Number": "5417XXXX2222", "mcc": "6011-Member ATM Cash", "Billing Amount": 100.0},
        {"Value Date": "28/09/2026 00:00:00", "Wallet Number": "W200", "Device Number": "5417XXXX2222", "mcc": "6011-Member ATM Cash", "Billing Amount": 100.0},
        {"Value Date": "28/09/2026 00:00:00", "Wallet Number": "W200", "Device Number": "5417XXXX2222", "mcc": "6011-Member ATM Cash", "Billing Amount": 100.0},
        {"Value Date": "28/09/2026 00:00:00", "Wallet Number": "W200", "Device Number": "5417XXXX2222", "mcc": "6011-Member ATM Cash", "Billing Amount": 100.0},
    ]
    df = pd.DataFrame(rows)

    res = run_task1_tms_atm(df, "pinelabs", "2026-09-28")
    assert res["flagged_individuals_count"] == 1
    alert = res["alerts"][0]
    assert alert["account_number"] == "W100"
    assert alert["individual_name"] == "5417XXXX1111"
    assert alert["transaction_frequency"] == 4
    assert alert["total_usd_equivalent"] == 1700.0
    assert len(res["flagged_transactions"]) == 4
    assert list(res["flagged_transactions"].columns) == list(df.columns)


def test_vegapay_task1_detection_logic():
    # Vegapay uses "Account Number", "Card Holder Name", "MCC", "Billing Amount", "Business Date"
    rows = [
        {"Business Date": "2026-10-15", "Account Number": "1000000000000999", "Card Holder Name": "John Doe", "MCC": "6011", "Billing Amount": 800.0},
        {"Business Date": "2026-10-15", "Account Number": "1000000000000999", "Card Holder Name": "John Doe", "MCC": "6011", "Billing Amount": 800.0},
        {"Business Date": "2026-10-15", "Account Number": "1000000000000999", "Card Holder Name": "John Doe", "MCC": "6011", "Billing Amount": 500.0},
        {"Business Date": "2026-10-15", "Account Number": "1000000000000999", "Card Holder Name": "John Doe", "MCC": "6011", "Billing Amount": 200.0},
    ]
    df = pd.DataFrame(rows)

    res = run_task1_tms_atm(df, "vegapay", "2026-10-15")
    assert res["flagged_individuals_count"] == 1
    alert = res["alerts"][0]
    assert alert["account_number"] == "1000000000000999"
    assert alert["individual_name"] == "John Doe"
    assert alert["transaction_frequency"] == 4
    assert alert["total_usd_equivalent"] == 2300.0
    assert len(res["flagged_transactions"]) == 4
    assert list(res["flagged_transactions"].columns) == list(df.columns)


# --- INTEGRATION & API TESTS ---

def test_task1_api_detect_and_exports(client):
    # 1. Create Session
    s_resp = client.post("/api/session")
    assert s_resp.status_code == 201
    s_id = s_resp.json()["session_id"]
    headers = {"X-Session-Id": s_id}

    # 2. Upload synthetic VISA file with headers
    rows = [
        {"spbusd": "2026-09-30", "spdate": "30092026", "spacct": "P999", "spname": "Alerted User", "spmcat": "6011", "spmusa": 500.0, "source_file": "batch1"},
        {"spbusd": "2026-09-30", "spdate": "30092026", "spacct": "P999", "spname": "Alerted User", "spmcat": "6011", "spmusa": 500.0, "source_file": "batch1"},
        {"spbusd": "2026-09-30", "spdate": "30092026", "spacct": "P999", "spname": "Alerted User", "spmcat": "6011", "spmusa": 500.0, "source_file": "batch1"},
        {"spbusd": "2026-09-30", "spdate": "30092026", "spacct": "P999", "spname": "Alerted User", "spmcat": "6011", "spmusa": 500.0, "source_file": "batch1"},
    ]
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False)
    file_bytes = buf.getvalue()

    upload_headers = {**headers, "X-Filename": "test_visa.xlsx"}
    up_resp = client.post("/api/task1/visa/upload", headers=upload_headers, content=file_bytes)
    assert up_resp.status_code == 200
    data = up_resp.json()
    assert data["ok"] is True
    assert "2026-09-30" in data["available_dates"]

    # 3. Detect alerts
    detect_resp = client.post(
        "/api/task1/visa/detect",
        headers=headers,
        json={"target_date": "2026-09-30"}
    )
    assert detect_resp.status_code == 200
    det_data = detect_resp.json()
    assert det_data["flagged_individuals_count"] == 1
    assert det_data["total_atm_transactions"] == 4
    assert len(det_data["preview_rows"]) == 4

    # 4. Export CSV
    csv_resp = client.get("/api/task1/export-csv", headers=headers)
    assert csv_resp.status_code == 200
    assert csv_resp.headers["content-type"].startswith("text/csv")
    assert "visa_tms_atm_flagged_2026-09-30.csv" in csv_resp.headers["content-disposition"]
    csv_text = csv_resp.content.decode("utf-8-sig")
    assert "P999" in csv_text
    assert "Alerted User" in csv_text

    # 5. Export Excel
    excel_resp = client.get("/api/task1/export-excel", headers=headers)
    assert excel_resp.status_code == 200
    assert excel_resp.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert "visa_tms_atm_flagged_2026-09-30.xlsx" in excel_resp.headers["content-disposition"]
    # Check openpyxl can read it
    df_read = pd.read_excel(io.BytesIO(excel_resp.content), engine="calamine")
    assert len(df_read) == 4
    assert list(df_read.columns) == list(df.columns)

    # 6. Export Alerts Summary CSV
    alerts_resp = client.get("/api/task1/export-alerts-csv", headers=headers)
    assert alerts_resp.status_code == 200
    assert "visa_tms_atm_alerts_summary_2026-09-30.csv" in alerts_resp.headers["content-disposition"]

    # 7. Export Specific Individual CSV
    indiv_csv_resp = client.get("/api/task1/export-csv?account_number=P999", headers=headers)
    assert indiv_csv_resp.status_code == 200
    assert "visa_tms_atm_P999_2026-09-30.csv" in indiv_csv_resp.headers["content-disposition"]
    indiv_csv_text = indiv_csv_resp.content.decode("utf-8-sig")
    assert "P999" in indiv_csv_text
    assert len(indiv_csv_text.strip().splitlines()) == 5  # header + 4 rows

    # 8. Export Specific Individual Excel
    indiv_excel_resp = client.get("/api/task1/export-excel?account_number=P999", headers=headers)
    assert indiv_excel_resp.status_code == 200
    assert "visa_tms_atm_P999_2026-09-30.xlsx" in indiv_excel_resp.headers["content-disposition"]
    df_indiv = pd.read_excel(io.BytesIO(indiv_excel_resp.content), engine="calamine")
    assert len(df_indiv) == 4
    assert set(df_indiv["spacct"]) == {"P999"}

    # 9. Non-existent account returns 404
    missing_resp = client.get("/api/task1/export-csv?account_number=NONEXISTENT", headers=headers)
    assert missing_resp.status_code == 404

    # 10. Date info verification
    assert det_data["date_info"]["column_name"] == "spbusd"
    assert "Business Date" in det_data["date_info"]["column_label"]


def test_task1_session_isolation(client):
    # Without session header
    resp = client.get("/api/task1/export-csv")
    assert resp.status_code == 401

    # With invalid session header
    resp = client.get("/api/task1/export-csv", headers={"X-Session-Id": "invalid_session_id"})
    assert resp.status_code == 401



def test_task1_date_normalization():
    s_visa = pd.Series(["2026-09-30", "30092026", "01102026", "-", ""])
    norm_v = normalize_date_series(s_visa, "visa")
    assert norm_v.iloc[0] == "2026-09-30"
    assert norm_v.iloc[1] == "2026-09-30"
    assert norm_v.iloc[2] == "2026-10-01"
    assert norm_v.iloc[3] == ""

    s_pine = pd.Series(["28/09/2026 00:00:00", "01/10/2026", "-"])
    norm_p = normalize_date_series(s_pine, "pinelabs")
    assert norm_p.iloc[0] == "2026-09-28"
    assert norm_p.iloc[1] == "2026-10-01"

    s_vega = pd.Series(["2026-10-15", "15-10-2026", "-"])
    norm_vg = normalize_date_series(s_vega, "vegapay")
    assert norm_vg.iloc[0] == "2026-10-15"
    assert norm_vg.iloc[1] == "2026-10-15"


def test_task1_empty_dataset_and_no_alerts():
    df_empty = pd.DataFrame(columns=["spbusd", "spdate", "spacct", "spname", "spmcat", "spmusa"])
    res = run_task1_tms_atm(df_empty, "visa", "2026-09-30")
    assert res["total_atm_transactions"] == 0
    assert res["flagged_individuals_count"] == 0
    assert len(res["alerts"]) == 0
    assert len(res["flagged_transactions"]) == 0


def test_task1_dates_and_sample_loading(client):
    s_resp = client.post("/api/session")
    s_id = s_resp.json()["session_id"]
    headers = {"X-Session-Id": s_id}

    # Query dates before upload -> 404
    resp = client.get("/api/task1/dates", headers=headers)
    assert resp.status_code == 404

    # Load sample
    sample_resp = client.post("/api/task1/visa/load-sample", headers=headers)
    assert sample_resp.status_code == 200
    sample_data = sample_resp.json()
    assert sample_data["ok"] is True
    assert len(sample_data["available_dates"]) > 0

    # Query dates now -> 200
    dates_resp = client.get("/api/task1/dates", headers=headers)
    assert dates_resp.status_code == 200
    assert len(dates_resp.json()["available_dates"]) > 0
