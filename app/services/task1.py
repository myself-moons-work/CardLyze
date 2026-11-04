"""Task 1: TMS-ATM High-Risk Transaction Monitoring Alert Service.

Requirements:
- Extract Spend data for previous 1 day (or user-chosen date).
- Filter by ATM MCCs (6011, 6010, 6050, 6051).
- Identify unique individuals using Account_Number or equivalent column:
  - VISA: spacct (Cardholder Name: spname)
  - PineLabs: Wallet Number (Device Number: Device Number)
  - Vegapay: Account Number (Cardholder Name: Card Holder Name, Customer ID: Customer ID)
- Identify individuals with transaction_frequency > 3.
- AND total USD Equivalent on these transactions > $1500.
- IF yes, individual gets +1 Alert with Date noted.
- Retrieve full un-modified original transactions for flagged individuals (zero column modification).
"""

from dataclasses import dataclass
import io
import re
from typing import Any, Dict, Generator, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from app.cards import is_null_token
from app.services.headers import iter_csv_chunks, to_xlsx_buffer

ATM_HIGH_RISK_MCCS: frozenset[str] = frozenset({"6011", "6010", "6050", "6051"})


@dataclass(frozen=True)
class Task1Alert:
    account_number: str
    individual_name: str
    alert_date: str
    transaction_frequency: int
    total_usd_equivalent: float
    alert_count: int = 1


def get_card_date_info(card_key: str) -> Dict[str, str]:
    """Return explicit metadata about the date column used for monitoring."""
    key = card_key.lower().strip()
    if key == "visa":
        return {
            "column_name": "spbusd",
            "column_label": "Business Date (spbusd)",
            "format": "YYYY-MM-DD",
            "description": "Bank settlement/ledger business date (spbusd). Daily batch extracts group records by this date.",
        }
    elif key == "pinelabs":
        return {
            "column_name": "Value Date",
            "column_label": "Value Date (Business Date)",
            "format": "DD/MM/YYYY HH:MM:SS",
            "description": "Core transaction value/business date. Daily batch extracts group records by this date.",
        }
    elif key == "vegapay":
        return {
            "column_name": "Business Date",
            "column_label": "Business Date",
            "format": "YYYY-MM-DD",
            "description": "Core accounting business date. Daily batch extracts group records by this date.",
        }
    return {
        "column_name": "Date",
        "column_label": "Date",
        "format": "YYYY-MM-DD",
        "description": "Target monitoring date",
    }


def normalize_date_series(s: pd.Series, card_key: str) -> pd.Series:
    """Normalize card date series to YYYY-MM-DD string format."""
    card_key = card_key.lower().strip()
    if len(s) == 0:
        return pd.Series(dtype="object")

    s_str = s.fillna("").astype(str).str.strip()

    if card_key == "visa":
        # spbusd is already YYYY-MM-DD; if spdate (DDMMYYYY) is passed
        def parse_visa_date(val: str) -> str:
            if not val or val in ("-", "None", "nan"):
                return ""
            if re.match(r"^\d{4}-\d{2}-\d{2}", val):
                return val[:10]
            val_clean = val.split(".")[0].zfill(8)
            if len(val_clean) == 8 and val_clean.isdigit():
                # DDMMYYYY -> YYYY-MM-DD
                dd, mm, yyyy = val_clean[:2], val_clean[2:4], val_clean[4:8]
                return f"{yyyy}-{mm}-{dd}"
            return ""
        return s_str.map(parse_visa_date)

    elif card_key == "pinelabs":
        # Value Date: 'DD/MM/YYYY HH:MM:SS' or 'DD/MM/YYYY'
        def parse_pine_date(val: str) -> str:
            if not val or val in ("-", "None", "nan"):
                return ""
            # Check YYYY-MM-DD
            if re.match(r"^\d{4}-\d{2}-\d{2}", val):
                return val[:10]
            match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", val)
            if match:
                d, m, y = match.group(1).zfill(2), match.group(2).zfill(2), match.group(3)
                return f"{y}-{m}-{d}"
            return ""
        return s_str.map(parse_pine_date)

    elif card_key == "vegapay":
        # Business Date: ISO YYYY-MM-DD; Transaction Date: DD-MM-YYYY
        def parse_vega_date(val: str) -> str:
            if not val or val in ("-", "None", "nan"):
                return ""
            if re.match(r"^\d{4}-\d{2}-\d{2}", val):
                return val[:10]
            match = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})", val)
            if match:
                d, m, y = match.group(1).zfill(2), match.group(2).zfill(2), match.group(3)
                return f"{y}-{m}-{d}"
            return ""
        return s_str.map(parse_vega_date)

    return s_str.str[:10]


def extract_mcc_code_series(s: pd.Series, card_key: str) -> pd.Series:
    """Extract 4-digit MCC code string from series."""
    card_key = card_key.lower().strip()
    s_str = s.fillna("").astype(str).str.strip()

    if card_key == "pinelabs":
        # e.g. "6011-Member Financial Institution..."
        return s_str.str.extract(r"^(\d{1,4})")[0].fillna("").astype(str).str.zfill(4)
    else:
        # e.g. "6011", 6011, "6011.0"
        return s_str.str.split(".").str[0].str.strip().str.zfill(4)


def get_available_dates(df: pd.DataFrame, card_key: str) -> List[str]:
    """Retrieve all distinct available dates from the dataset (formatted YYYY-MM-DD)."""
    card_key = card_key.lower().strip()
    date_col = None
    if card_key == "visa":
        date_col = "spbusd" if "spbusd" in df.columns else "spdate"
    elif card_key == "pinelabs":
        date_col = "Value Date" if "Value Date" in df.columns else "Transaction Date"
    elif card_key == "vegapay":
        date_col = "Business Date" if "Business Date" in df.columns else "Transaction Date"

    if date_col is None or date_col not in df.columns or len(df) == 0:
        return []

    norm_dates = normalize_date_series(df[date_col], card_key)
    valid_dates = [d for d in norm_dates.unique() if d and d != ""]
    valid_dates.sort(reverse=True)
    return valid_dates


def run_task1_tms_atm(
    df: pd.DataFrame,
    card_key: str,
    target_date: str,
    frequency_threshold: int = 3,
    usd_threshold: float = 1500.0,
) -> Dict[str, Any]:
    """Execute Task 1 TMS-ATM Alert Detection for a single date.
    
    Returns:
    - target_date: str (YYYY-MM-DD)
    - card_key: str
    - total_atm_transactions: int
    - flagged_individuals_count: int
    - alerts: List[Dict[str, Any]] (Account, Name/PAN, Date, Freq, Total USD, Alert Count)
    - flagged_transactions: pd.DataFrame (Original un-modified rows for flagged individuals)
    """
    card_key = card_key.lower().strip()
    if len(df) == 0:
        return {
            "target_date": target_date,
            "card_key": card_key,
            "total_atm_transactions": 0,
            "flagged_individuals_count": 0,
            "alerts": [],
            "flagged_transactions": pd.DataFrame(columns=df.columns),
        }

    # 1. Resolve Columns per Card
    if card_key == "visa":
        date_col = "spbusd" if "spbusd" in df.columns else "spdate"
        mcc_col = "spmcat"
        acct_col = "spacct"
        name_col = "spname"
        usd_col = "spmusa"
    elif card_key == "pinelabs":
        date_col = "Value Date" if "Value Date" in df.columns else "Transaction Date"
        mcc_col = "mcc"
        acct_col = "Wallet Number"
        name_col = "Device Number"  # PineLabs does not have cardholder name
        usd_col = "Billing Amount"
    elif card_key == "vegapay":
        date_col = "Business Date" if "Business Date" in df.columns else "Transaction Date"
        mcc_col = "MCC"
        acct_col = "Account Number"
        name_col = "Card Holder Name"
        usd_col = "Billing Amount"
    else:
        raise ValueError(f"Unknown card key: {card_key}")

    # Check necessary columns exist
    for col in (date_col, mcc_col, acct_col, usd_col):
        if col not in df.columns:
            raise ValueError(f"Missing required column '{col}' for card '{card_key}'")

    # 2. Date Filtering
    norm_dates = normalize_date_series(df[date_col], card_key)
    date_mask = norm_dates == target_date
    df_date = df[date_mask]

    if len(df_date) == 0:
        return {
            "target_date": target_date,
            "card_key": card_key,
            "total_atm_transactions": 0,
            "flagged_individuals_count": 0,
            "alerts": [],
            "flagged_transactions": pd.DataFrame(columns=df.columns),
        }

    # 3. Filter by High-Risk ATM MCCs (6011, 6010, 6050, 6051)
    mcc_codes = extract_mcc_code_series(df_date[mcc_col], card_key)
    atm_mask = mcc_codes.isin(ATM_HIGH_RISK_MCCS)
    df_atm = df_date[atm_mask].copy()

    total_atm_count = len(df_atm)
    if total_atm_count == 0:
        return {
            "target_date": target_date,
            "card_key": card_key,
            "total_atm_transactions": 0,
            "flagged_individuals_count": 0,
            "alerts": [],
            "flagged_transactions": pd.DataFrame(columns=df.columns),
        }

    # 4. Parse USD Amount Column as Float
    usd_series = pd.to_numeric(
        df_atm[usd_col].astype(str).str.replace(",", "").str.strip(),
        errors="coerce"
    ).fillna(0.0).abs()

    # 5. Group by Unique Individual (acct_col)
    acct_series = df_atm[acct_col].astype(str).str.strip()
    
    # Calculate Frequency and USD Sum per individual
    grouped_stats = {}
    for idx, (acct, usd_val) in enumerate(zip(acct_series, usd_series)):
        if acct not in grouped_stats:
            name_val = str(df_atm[name_col].iloc[idx]) if name_col in df_atm.columns else ""
            grouped_stats[acct] = {
                "count": 0,
                "total_usd": 0.0,
                "name": name_val,
                "row_indices": []
            }
        grouped_stats[acct]["count"] += 1
        grouped_stats[acct]["total_usd"] += usd_val
        grouped_stats[acct]["row_indices"].append(df_atm.index[idx])

    # 6. Flag individuals where frequency > threshold AND total_usd > usd_threshold
    flagged_alerts: List[Dict[str, Any]] = []
    flagged_indices: List[int] = []

    # Sort individuals by total_usd descending
    sorted_individuals = sorted(
        grouped_stats.items(),
        key=lambda item: item[1]["total_usd"],
        reverse=True
    )

    for acct, stats in sorted_individuals:
        if stats["count"] > frequency_threshold and stats["total_usd"] > usd_threshold:
            flagged_alerts.append({
                "account_number": acct,
                "individual_name": stats["name"],
                "alert_date": target_date,
                "transaction_frequency": stats["count"],
                "total_usd_equivalent": round(float(stats["total_usd"]), 2),
                "alert_count": 1,
            })
            flagged_indices.extend(stats["row_indices"])

    # 7. Retrieve full un-modified original transaction rows
    if flagged_indices:
        # Preserve original un-modified DataFrame slice with EXACT original columns
        flagged_df = df.loc[flagged_indices].copy()
    else:
        flagged_df = pd.DataFrame(columns=df.columns)

    return {
        "target_date": target_date,
        "card_key": card_key,
        "total_atm_transactions": total_atm_count,
        "flagged_individuals_count": len(flagged_alerts),
        "alerts": flagged_alerts,
        "flagged_transactions": flagged_df,
        "date_info": get_card_date_info(card_key),
    }


def stream_task1_csv(df: pd.DataFrame) -> Generator[bytes, None, None]:
    """Stream unmodified transactions as UTF-8 BOM CSV in chunks."""
    return iter_csv_chunks(df, chunk_size=10000)


def build_task1_excel(df: pd.DataFrame) -> io.BytesIO:
    """Build in-memory Excel file of unmodified transactions."""
    return to_xlsx_buffer(df)

