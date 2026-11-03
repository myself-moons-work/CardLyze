"""Card configurations, schema definitions, and explicit parsing utilities.

This module is the SINGLE SOURCE OF TRUTH for card definitions in CardLyze.
"""

from collections import Counter
from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Set, Union
import pandas as pd

# Known placeholder / null tokens treated as blank without warning
NULL_TOKENS: frozenset[str] = frozenset({
    "-", "--", "---", "", "None", "none", "nan", "NaN", "NAT", "NaT", "null", "NULL"
})
DEFAULT_EPOCH_DOB = pd.Timestamp("1970-01-01")

# Standard ISO 3166-1 alpha-2 country codes
ISO_3166_1_ALPHA2: frozenset[str] = frozenset({
    "AD", "AE", "AF", "AG", "AI", "AL", "AM", "AO", "AQ", "AR", "AS", "AT", "AU", "AW", "AX", "AZ",
    "BA", "BB", "BD", "BE", "BF", "BG", "BH", "BI", "BJ", "BL", "BM", "BN", "BO", "BQ", "BR", "BS",
    "BT", "BV", "BW", "BY", "BZ", "CA", "CC", "CD", "CF", "CG", "CH", "CI", "CK", "CL", "CM", "CN",
    "CO", "CR", "CU", "CV", "CW", "CX", "CY", "CZ", "DE", "DJ", "DK", "DM", "DO", "DZ", "EC", "EE",
    "EG", "EH", "ER", "ES", "ET", "FI", "FJ", "FK", "FM", "FO", "FR", "GA", "GB", "GD", "GE", "GF",
    "GG", "GH", "GI", "GL", "GM", "GN", "GP", "GQ", "GR", "GS", "GT", "GU", "GW", "GY", "HK", "HM",
    "HN", "HR", "HT", "HU", "ID", "IE", "IL", "IM", "IN", "IO", "IQ", "IR", "IS", "IT", "JE", "JM",
    "JO", "JP", "KE", "KG", "KH", "KI", "KM", "KN", "KP", "KR", "KW", "KY", "KZ", "LA", "LB", "LC",
    "LI", "LK", "LR", "LS", "LT", "LU", "LV", "LY", "MA", "MC", "MD", "ME", "MF", "MG", "MH", "MK",
    "ML", "MM", "MN", "MO", "MP", "MQ", "MR", "MS", "MT", "MU", "MV", "MW", "MX", "MY", "MZ", "NA",
    "NC", "NE", "NF", "NG", "NI", "NL", "NO", "NP", "NR", "NU", "NZ", "OM", "PA", "PE", "PF", "PG",
    "PH", "PK", "PL", "PM", "PN", "PR", "PS", "PT", "PW", "PY", "QA", "RE", "RO", "RS", "RU", "RW",
    "SA", "SB", "SC", "SD", "SE", "SG", "SH", "SI", "SJ", "SK", "SL", "SM", "SN", "SO", "SR", "SS",
    "ST", "SV", "SX", "SY", "SZ", "TC", "TD", "TF", "TG", "TH", "TJ", "TK", "TL", "TM", "TN", "TO",
    "TR", "TT", "TV", "TW", "TZ", "UA", "UG", "UM", "US", "UY", "UZ", "VA", "VC", "VE", "VG", "VI",
    "VN", "VU", "WF", "WS", "YE", "YT", "ZA", "ZM", "ZW"
})

# Complete ISO 3166-1 alpha-3 to alpha-2 mappings (249 officially assigned codes)
ISO_3166_1_ALPHA3_TO_ALPHA2: Dict[str, str] = {
    "ABW": "AW", "AFG": "AF", "AGO": "AO", "AIA": "AI", "ALA": "AX", "ALB": "AL",
    "AND": "AD", "ARE": "AE", "ARG": "AR", "ARM": "AM", "ASM": "AS", "ATA": "AQ",
    "ATF": "TF", "ATG": "AG", "AUS": "AU", "AUT": "AT", "AZE": "AZ", "BDI": "BI",
    "BEL": "BE", "BEN": "BJ", "BES": "BQ", "BFA": "BF", "BGD": "BD", "BGR": "BG",
    "BHR": "BH", "BHS": "BS", "BIH": "BA", "BLM": "BL", "BLR": "BY", "BLZ": "BZ",
    "BMU": "BM", "BOL": "BO", "BRA": "BR", "BRB": "BB", "BRN": "BN", "BTN": "BT",
    "BVT": "BV", "BWA": "BW", "CAF": "CF", "CAN": "CA", "CCK": "CC", "CHE": "CH",
    "CHL": "CL", "CHN": "CN", "CIV": "CI", "CMR": "CM", "COD": "CD", "COG": "CG",
    "COK": "CK", "COL": "CO", "COM": "KM", "CPV": "CV", "CRI": "CR", "CUB": "CU",
    "CUW": "CW", "CXR": "CX", "CYM": "KY", "CYP": "CY", "CZE": "CZ", "DEU": "DE",
    "DJI": "DJ", "DMA": "DM", "DNK": "DK", "DOM": "DO", "DZA": "DZ", "ECU": "EC",
    "EGY": "EG", "ERI": "ER", "ESH": "EH", "ESP": "ES", "EST": "EE", "ETH": "ET",
    "FIN": "FI", "FJI": "FJ", "FLK": "FK", "FRA": "FR", "FRO": "FO", "FSM": "FM",
    "GAB": "GA", "GBR": "GB", "GEO": "GE", "GGY": "GG", "GHA": "GH", "GIB": "GI",
    "GIN": "GN", "GLP": "GP", "GMB": "GM", "GNB": "GW", "GNQ": "GQ", "GRC": "GR",
    "GRD": "GD", "GRL": "GL", "GTM": "GT", "GUF": "GF", "GUM": "GU", "GUY": "GY",
    "HKG": "HK", "HMD": "HM", "HND": "HN", "HRV": "HR", "HTI": "HT", "HUN": "HU",
    "IDN": "ID", "IMN": "IM", "IND": "IN", "IOT": "IO", "IRL": "IE", "IRN": "IR",
    "IRQ": "IQ", "ISL": "IS", "ISR": "IL", "ITA": "IT", "JAM": "JM", "JEY": "JE",
    "JOR": "JO", "JPN": "JP", "KAZ": "KZ", "KEN": "KE", "KGZ": "KG", "KHM": "KH",
    "KIR": "KI", "KNA": "KN", "KOR": "KR", "KWT": "KW", "LAO": "LA", "LBN": "LB",
    "LBR": "LR", "LBY": "LY", "LCA": "LC", "LIE": "LI", "LKA": "LK", "LSO": "LS",
    "LTU": "LT", "LUX": "LU", "LVA": "LV", "MAC": "MO", "MAF": "MF", "MAR": "MA",
    "MCO": "MC", "MDA": "MD", "MDG": "MG", "MDV": "MV", "MEX": "MX", "MHL": "MH",
    "MKD": "MK", "MLI": "ML", "MLT": "MT", "MMR": "MM", "MNE": "ME", "MNG": "MN",
    "MNP": "MP", "MOZ": "MZ", "MRT": "MR", "MSR": "MS", "MTQ": "MQ", "MUS": "MU",
    "MWI": "MW", "MYS": "MY", "MYT": "YT", "NAM": "NA", "NCL": "NC", "NER": "NE",
    "NFK": "NF", "NGA": "NG", "NIC": "NI", "NIU": "NU", "NLD": "NL", "NOR": "NO",
    "NPL": "NP", "NRU": "NR", "NZL": "NZ", "OMN": "OM", "PAK": "PK", "PAN": "PA",
    "PCN": "PN", "PER": "PE", "PHL": "PH", "PLW": "PW", "PNG": "PG", "POL": "PL",
    "PRI": "PR", "PRK": "KP", "PRT": "PT", "PRY": "PY", "PSE": "PS", "PYF": "PF",
    "QAT": "QA", "REU": "RE", "ROU": "RO", "RUS": "RU", "RWA": "RW", "SAU": "SA",
    "SDN": "SD", "SEN": "SN", "SGP": "SG", "SGS": "GS", "SHN": "SH", "SJM": "SJ",
    "SLB": "SB", "SLE": "SL", "SLV": "SV", "SMR": "SM", "SOM": "SO", "SPM": "PM",
    "SRB": "RS", "SSD": "SS", "STP": "ST", "SUR": "SR", "SVK": "SK", "SVN": "SI",
    "SWE": "SE", "SWZ": "SZ", "SXM": "SX", "SYC": "SC", "SYR": "SY", "TCA": "TC",
    "TCD": "TD", "TGO": "TG", "THA": "TH", "TJK": "TJ", "TKL": "TK", "TKM": "TM",
    "TLS": "TL", "TON": "TO", "TTO": "TT", "TUN": "TN", "TUR": "TR", "TUV": "TV",
    "TWN": "TW", "TZA": "TZ", "UGA": "UG", "UKR": "UA", "UMI": "UM", "URY": "UY",
    "USA": "US", "UZB": "UZ", "VAT": "VA", "VCT": "VC", "VEN": "VE", "VGB": "VG",
    "VIR": "VI", "VNM": "VN", "VUT": "VU", "WLF": "WF", "WSM": "WS", "YEM": "YE",
    "ZAF": "ZA", "ZMB": "ZM", "ZWE": "ZW",
}

# Common full country name mapping fallback
COUNTRY_NAME_TO_ALPHA2: Dict[str, str] = {
    "UNITED STATES": "US", "UNITED STATES OF AMERICA": "US", "USA": "US",
    "UNITED KINGDOM": "GB", "GREAT BRITAIN": "GB", "UK": "GB",
    "INDIA": "IN", "BHARAT": "IN",
    "UNITED ARAB EMIRATES": "AE", "UAE": "AE",
    "SINGAPORE": "SG", "AUSTRALIA": "AU", "CANADA": "CA",
    "GERMANY": "DE", "FRANCE": "FR", "NETHERLANDS": "NL", "SWEDEN": "SE",
    "THAILAND": "TH", "JAPAN": "JP", "ITALY": "IT", "HONG KONG": "HK",
    "MALAYSIA": "MY", "BOTSWANA": "BW", "FINLAND": "FI", "GEORGIA": "GE",
    "SOUTH KOREA": "KR", "KOREA": "KR", "SPAIN": "ES", "VIETNAM": "VN",
    "BELGIUM": "BE", "AUSTRIA": "AT", "SWITZERLAND": "CH", "INDONESIA": "ID",
    "QATAR": "QA", "SAUDI ARABIA": "SA",
}

# Explicit date parsing configurations
# Addendum 3 confirmation status:
# - Vegapay: Mastercard Date, Transaction Date and DOB are dd-mm-yyyy (CONFIRMED).
#   Business Date and Settlement Date are ISO yyyy-mm-dd (CONFIRMED).
#   "-" is a placeholder in Mastercard Date, Transaction Date and Settlement Date (CONFIRMED).
# - PineLabs: Formats marked to confirm against real data.
# - VISA: Formats marked to confirm against real data (pad=8 confirmed for spdate).
DATE_CONFIGS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "Vegapay": {
        # Confirmed ISO format from real Vegapay file
        "Business Date": {"formats": ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S"]},
        # Confirmed dd-mm-yyyy format from real Vegapay file
        "DOB": {"formats": ["%d-%m-%Y", "%d-%m-%Y %H:%M:%S"]},
        # Confirmed dd-mm-yyyy format from real Vegapay file; '-' is a confirmed placeholder
        "Mastercard Date": {"formats": ["%d-%m-%Y", "%d-%m-%Y %H:%M:%S"]},
        # Confirmed dd-mm-yyyy format from real Vegapay file; '-' is a confirmed placeholder
        "Transaction Date": {"formats": ["%d-%m-%Y", "%d-%m-%Y %H:%M:%S"]},
        # Confirmed ISO format from real Vegapay file; '-' is a confirmed placeholder
        "Settlement Date": {"formats": ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S"]},
    },
    "PineLabs": {
        # Assumption to confirm against real data
        "Value Date": {"formats": ["%d/%m/%Y %H:%M:%S", "%d/%m/%Y"]},
        # Assumption to confirm against real data
        "Transaction Date": {"formats": ["%d/%m/%Y %H:%M:%S", "%d/%m/%Y"]},
    },
    "VISA": {
        # Assumption to confirm against real data
        "spbusd": {"formats": ["%Y-%m-%d"]},
        # DDMMYYYY with mandatory 8-digit left padding (pad=8 confirmed to avoid 7-digit misparse)
        "spdate": {"formats": ["%d%m%Y"], "pad": 8},
    },
}


@dataclass(frozen=True)
class CardConfig:
    """Card configuration schema definition."""
    key: str
    label: str
    expected_columns: List[str]
    numeric_cols: List[str]
    date_cols: Dict[str, Dict[str, Any]]
    id_like_cols: List[str]
    mcc_col: str
    sensitive_cols: List[str]
    key_cols: List[str]
    pad_cols: Dict[str, int] = field(default_factory=dict)
    country_confidence: str = "derived"
    country_formats: List[str] = field(default_factory=lambda: ["alpha2"])
    pad_mcc_to_4: bool = False


# --- VISA Card Configuration ---
VISA_EXPECTED_COLUMNS: List[str] = [
    "spbusd", "spbin", "spdesc", "spacct", "spname", "spctyp", "spcnam",
    "spcard", "spczid", "spmcat", "SPTRN$", "sptrcc", "spdbcr", "sppucc",
    "sputa", "spfeam", "spfgst", "spmrkp", "spmgst", "spptam", "spmusa",
    "sptdes", "spldes", "spstan", "spdate", "sptime", "spcaid", "spcati",
    "source_file",
]

VISA_NUMERIC_COLS: List[str] = [
    "SPTRN$", "sputa", "spfeam", "spfgst", "spmrkp", "spmgst", "spptam", "spmusa",
]

VISA_ID_LIKE_COLS: List[str] = [
    "spbin", "spacct", "spcard", "spczid", "spmcat", "sptrcc", "sppucc",
    "spstan", "spcaid", "spcati",
]

VISA_SENSITIVE_COLS: List[str] = [
    "spcard", "spacct", "spname", "spcnam",
]

VISA_KEY_COLS: List[str] = [
    "spbusd", "spdate", "sptime", "spacct", "spname", "spmcat",
    "SPTRN$", "sputa", "sptdes", "spldes", "source_file",
]

# Confirmed padding width for lost leading zeros in VISA
VISA_PAD_COLS: Dict[str, int] = {
    "spdate": 8,
    "spcati": 8,
}


# --- PineLabs Card Configuration ---
PINELABS_EXPECTED_COLUMNS: List[str] = [
    "Product Type", "Value Date", "Program Name", "channel", "Transaction Origin",
    "Transaction Code", "Transaction Type", "Device Type", "Device Number",
    "Authorization Number", "arn", "Transaction Currency", "Transaction Amount",
    "Settlement Currency", "Settlement Amount", "Billing Currency", "Billing Amount",
    "Conversion Rate", "Transaction Date", "Markup Fee", "Card Acceptor ID",
    "Total Fees Currency", "Total Fees & Charges", "Reversal Flag", "Terminal ID",
    "ECOMM Indicator", "UCAF Indicator", "Transaction Fees", "Tax Amount", "mcc",
    "Tolerance Type", "Tolerance Unit", "CBS Transaction ID",
    "Foreign Currency Transaction", "Agent Entity Name", "Branch Entity ID",
    "Branch Entity Name", "Agency Name", "Wallet Number", "Trace Audit Number",
    "Merchant Name & Location", "Settlement Date", "MultiClearing Indicator",
    "MultiClearing Total Amount", "MultiClearing Seq No", "MultiClearing Seq Count",
    "DR/CR to Cardholder", "DCC Pre-Conversion Amount", "DCC Pre-Conversion Currency",
    "Corporate Name", "Transaction Originated From", "Device Number Alias", "memo",
    "Virtual Card Number", "Cashback Amount", "Cashback Currency", "Partial Approval",
    "Card Pack Id", "Corporate Id", "Travel Type", "Token Transaction Type",
    "Loyalty Points Earned", "CUSTOM DATA 1", "CUSTOM DATA 2", "Reference Number",
    "State/Province", "Recurring Additional Data", "source_file",
]

PINELABS_NUMERIC_COLS: List[str] = [
    "Transaction Amount", "Settlement Amount", "Billing Amount", "Conversion Rate",
    "Markup Fee", "Total Fees & Charges", "Transaction Fees", "Tax Amount",
    "Tolerance Unit", "Loyalty Points Earned",
]

PINELABS_ID_LIKE_COLS: List[str] = [
    "Device Number", "Authorization Number", "arn", "Terminal ID", "mcc",
    "CBS Transaction ID", "Wallet Number", "Trace Audit Number",
    "Virtual Card Number", "Card Pack Id", "Corporate Id", "Reference Number",
]

PINELABS_SENSITIVE_COLS: List[str] = [
    "Wallet Number", "Virtual Card Number", "Device Number",
]

PINELABS_KEY_COLS: List[str] = [
    "Value Date", "Transaction Date", "Program Name", "channel", "mcc",
    "Transaction Amount", "Transaction Currency", "Billing Amount",
    "Merchant Name & Location", "Terminal ID", "Transaction Type", "Reversal Flag",
]

PINELABS_PAD_COLS: Dict[str, int] = {
    "Terminal ID": 8,
}


# --- Vegapay Card Configuration ---
VEGAPAY_EXPECTED_COLUMNS: List[str] = [
    "Business Date", "Customer ID", "BIN", "Product Description", "AccountId",
    "Account Number", "Transaction Number", "Card Holder Name", "DOB",
    "Passport Number", "Cardholder Type", "Corporate Name", "Card Number",
    "Card proxy Id", "MCC", "MCC Description", "Mastercard Date", "Mastercard Time",
    "Days count", "Transaction Amount", "Transaction Currency", "Dr/Cr",
    "Posted Wallet Currency", "Posted Transaction Wallet Amount", "Posted Fee Amount",
    "Posted Fee GST", "Posted Markup Fee", "Posted Markup Fee GST",
    "Total CPF Posted Wallet Amount", "Transaction Description", "Decline Reason",
    "Merchant Name", "Long Adjustment Description", "Transaction Id",
    "Authorization Number", "Mer Code", "Merchant City", "Merchant Country", "RRN",
    "Settlement Amount", "Settlement Currency", "Billing Amount", "Billing Currency",
    "Transaction Code", "Transaction Code Narration", "Terminal ID", "Transaction Date",
    "Transaction Time", "ARN", "MultiClearing Indicator", "Transaction Type",
    "Settlement Date", "Settlement Time", "Reversal Flag", "ISIC Serial Number",
    "source_file", "Balance Enquiry Fee", "Balance Enquiry Fee GST",
    "Cash Withdrawal fee", "Cash Withdrawal Fee GST", "program",
]

VEGAPAY_NUMERIC_COLS: List[str] = [
    "Days count", "Transaction Amount", "Posted Transaction Wallet Amount",
    "Posted Fee Amount", "Posted Fee GST", "Posted Markup Fee", "Posted Markup Fee GST",
    "Total CPF Posted Wallet Amount", "Settlement Amount", "Billing Amount",
    "Balance Enquiry Fee", "Balance Enquiry Fee GST", "Cash Withdrawal fee",
    "Cash Withdrawal Fee GST",
]

VEGAPAY_ID_LIKE_COLS: List[str] = [
    "Customer ID", "BIN", "AccountId", "Account Number", "Transaction Number",
    "Card Number", "Card proxy Id", "MCC", "Transaction Id", "Authorization Number",
    "Mer Code", "RRN", "Transaction Code", "Terminal ID", "ARN", "ISIC Serial Number",
]

VEGAPAY_SENSITIVE_COLS: List[str] = [
    "Passport Number", "DOB", "Card Number", "Account Number", "Customer ID",
]

VEGAPAY_KEY_COLS: List[str] = [
    "Business Date", "Transaction Date", "Settlement Date", "Card Holder Name",
    "Transaction Amount", "Transaction Currency", "MCC", "MCC Description",
    "Merchant Name", "Merchant City", "Merchant Country", "Transaction Description", "Dr/Cr",
]

VEGAPAY_PAD_COLS: Dict[str, int] = {
    "Terminal ID": 8,
}


CARDS: Dict[str, CardConfig] = {
    "visa": CardConfig(
        key="visa",
        label="VISA",
        expected_columns=VISA_EXPECTED_COLUMNS,
        numeric_cols=VISA_NUMERIC_COLS,
        date_cols=DATE_CONFIGS["VISA"],
        id_like_cols=VISA_ID_LIKE_COLS,
        mcc_col="spmcat",
        sensitive_cols=VISA_SENSITIVE_COLS,
        key_cols=VISA_KEY_COLS,
        pad_cols=VISA_PAD_COLS,
        country_confidence="derived",
        country_formats=["alpha2"],
    ),
    "pinelabs": CardConfig(
        key="pinelabs",
        label="PineLabs",
        expected_columns=PINELABS_EXPECTED_COLUMNS,
        numeric_cols=PINELABS_NUMERIC_COLS,
        date_cols=DATE_CONFIGS["PineLabs"],
        id_like_cols=PINELABS_ID_LIKE_COLS,
        mcc_col="mcc",
        sensitive_cols=PINELABS_SENSITIVE_COLS,
        key_cols=PINELABS_KEY_COLS,
        pad_cols=PINELABS_PAD_COLS,
        country_confidence="derived",
        country_formats=["alpha3"],
        pad_mcc_to_4=True,
    ),
    "vegapay": CardConfig(
        key="vegapay",
        label="Vegapay",
        expected_columns=VEGAPAY_EXPECTED_COLUMNS,
        numeric_cols=VEGAPAY_NUMERIC_COLS,
        date_cols=DATE_CONFIGS["Vegapay"],
        id_like_cols=VEGAPAY_ID_LIKE_COLS,
        mcc_col="MCC",
        sensitive_cols=VEGAPAY_SENSITIVE_COLS,
        key_cols=VEGAPAY_KEY_COLS,
        pad_cols=VEGAPAY_PAD_COLS,
        country_confidence="exact",
        country_formats=["alpha2", "alpha3"],
    ),
}


def get_card_config(card: Union[str, CardConfig, Dict[str, Any]]) -> CardConfig:
    """Resolve a card key, name, or config object into a canonical CardConfig."""
    if isinstance(card, CardConfig):
        return card
    if isinstance(card, dict) and "key" in card:
        key = str(card["key"]).lower()
    else:
        key = str(card).lower()

    if key not in CARDS:
        valid_keys = ", ".join(CARDS.keys())
        raise ValueError(f"Unknown card type '{card}'. Valid card types are: {valid_keys}")
    return CARDS[key]


# --- Column Padding for Lost Leading Zeros ---

def pad_column(series: pd.Series, width: int) -> tuple[pd.Series, int]:
    """Left-pad digit-only strings with leading zeros to width.
    Preserves NULL_TOKENS, blanks, non-digits, and alphanumeric values as-is.
    Returns (padded_series, count_of_padded_values).
    """
    if not isinstance(series, pd.Series):
        series = pd.Series(series)

    padded_count = 0

    def _pad(val: Any) -> Any:
        nonlocal padded_count
        if val is None or pd.isna(val):
            return val
        s = str(val).strip()
        if s in NULL_TOKENS or not s:
            return s
        # (a) Pad only values that are entirely digits and shorter than width;
        # leave alphanumeric values alone (e.g. '3A' stays '3A')
        if s.isdigit() and len(s) < width:
            padded_count += 1
            return s.zfill(width)
        return s

    out = series.apply(_pad)
    return out, padded_count


def apply_column_padding(
    df: pd.DataFrame,
    card: Union[str, CardConfig, Dict[str, Any]],
) -> tuple[pd.DataFrame, Dict[str, int]]:
    """Apply configured leading-zero padding to digit-only values in relevant columns.
    Returns (padded_df, padded_counts_dict).
    Stores original untouched values in hidden `_raw_<col>` columns so nothing is lost.
    """
    card_cfg = get_card_config(card)
    padded_counts: Dict[str, int] = {}
    if not card_cfg.pad_cols:
        return df.copy(), padded_counts

    out_df = df.copy()
    for col, width in card_cfg.pad_cols.items():
        if col in out_df.columns:
            # Keep original untouched value available
            out_df[f"_raw_{col}"] = out_df[col]
            padded_col, count = pad_column(out_df[col], width)
            out_df[col] = padded_col
            padded_counts[col] = count
    return out_df, padded_counts


# --- Country Code Derivation ---

def validate_iso_country(raw_token: Any, allow_alpha3: bool = False) -> str:
    """Validate raw country token against ISO 3166-1 alpha-2 standards (and optionally alpha-3 for Vegapay).
    Returns uppercase 2-letter alpha-2 code, or 'Unknown'.
    """
    if raw_token is None or pd.isna(raw_token):
        return "Unknown"
    token = str(raw_token).strip().upper()
    if not token or token in NULL_TOKENS:
        return "Unknown"

    # Strip surrounding punctuation (e.g. 'US.' -> 'US', '(GB)' -> 'GB')
    clean = token.strip(".,;:/-()[]{}'\"")
    if clean in ISO_3166_1_ALPHA2:
        return clean
    if allow_alpha3:
        if clean in ISO_3166_1_ALPHA3_TO_ALPHA2:
            return ISO_3166_1_ALPHA3_TO_ALPHA2[clean]
        if clean in COUNTRY_NAME_TO_ALPHA2:
            return COUNTRY_NAME_TO_ALPHA2[clean]

    return "Unknown"


def derive_country(df: pd.DataFrame, card: Union[str, CardConfig, Dict[str, Any]]) -> pd.Series:
    """Derive standardized 2-letter country_code Series validated against ISO 3166-1.
    
    Rules:
    - Vegapay: Sourced from 'Merchant Country' (accepts alpha-2, alpha-3, or common full country names).
    - VISA: Derived from last token of 'spldes' (e.g., 'BLUE MART FRESH MINI DUBAI AE' -> 'AE').
      Validated against ISO 3166-1 alpha-2; otherwise 'Unknown'.
    - PineLabs: Evaluates tokens from the end of 'Merchant Name & Location' for the last 2-letter
      uppercase ISO alpha-2 code, else 'Unknown'.
      NOTE on False Positives: Words like 'TO' (Tonga) or 'IN' (India) are valid ISO codes.
      Checking the trailing position is safe because merchant descriptors place acquirer location
      at the end (e.g. 'MERCHANT NAME CITY IN'). Prepositions within names ('PAY TO') are mid-string.
    """
    card_cfg = get_card_config(card)
    card_key = card_cfg.key

    if card_key == "vegapay":
        col = "Merchant Country"
        if col in df.columns:
            res = df[col].apply(lambda v: validate_iso_country(v, allow_alpha3=True))
        else:
            res = pd.Series("Unknown", index=df.index)

    elif card_key == "visa":
        col = "spldes"
        if col in df.columns:
            def _extract_visa(val: Any) -> str:
                if val is None or pd.isna(val):
                    return "Unknown"
                tokens = str(val).strip().split()
                if not tokens:
                    return "Unknown"
                return validate_iso_country(tokens[-1], allow_alpha3=False)

            res = df[col].apply(_extract_visa)
        else:
            res = pd.Series("Unknown", index=df.index)

    elif card_key == "pinelabs":
        col = "Merchant Name & Location"
        if col in df.columns:
            def _extract_pinelabs(val: Any) -> str:
                """PineLabs country derivation: checks LAST whitespace token only.
                Must be uppercase, 3 letters, and present in ISO_3166_1_ALPHA3_TO_ALPHA2.
                Normalizes to 2-letter ISO code, otherwise returns 'Unknown'.
                Does not use alpha-2 to avoid US state code collisions (e.g. CA, ME, VA, IL).

                NOTE on False Positives:
                Real words that are valid ISO alpha-3 codes (AND, ARE, CAN, COM, MAR, DOM, PER, SEN)
                can cause false positives when appearing as the trailing token of merchant names.
                The Transaction Currency cross-check is meant to catch and verify these cases.
                """
                if val is None or pd.isna(val):
                    return "Unknown"
                text = str(val).strip()
                if not text or text in NULL_TOKENS:
                    return "Unknown"
                tokens = text.split()
                if not tokens:
                    return "Unknown"
                last_tok = tokens[-1].strip(".,;:/-()[]{}'\"")
                if len(last_tok) == 3 and last_tok.isupper() and last_tok in ISO_3166_1_ALPHA3_TO_ALPHA2:
                    return ISO_3166_1_ALPHA3_TO_ALPHA2[last_tok]
                return "Unknown"

            res = df[col].apply(_extract_pinelabs)
        else:
            res = pd.Series("Unknown", index=df.index)

    else:
        res = pd.Series("Unknown", index=df.index)

    res.name = "country_code"
    return res


# --- MCC Normalization ---

def derive_mcc(
    df: pd.DataFrame,
    card: Union[str, CardConfig, Dict[str, Any]],
    return_pad_count: bool = False,
) -> Union[tuple[pd.Series, pd.Series], tuple[pd.Series, pd.Series, int]]:
    """Derive normalized `mcc_code` and `mcc_description` columns for the Analysis path.
    
    Rules:
    - PineLabs: 'mcc' holds '<digits>-<description>' in one string.
      Parses leading 1-4 digits into mcc_code and remainder into mcc_description.
      Placeholders (e.g. '-') or non-matches become empty strings.
    - Vegapay: 'MCC' is mcc_code, 'MCC Description' is mcc_description.
    - VISA: 'spmcat' is mcc_code, mcc_description is empty string.
    - Optional zero-padding to 4 digits (digit-only) applied if card_cfg.pad_mcc_to_4 is True.
      Returns (s_code, s_desc, pad_count) when return_pad_count=True.
    """
    card_cfg = get_card_config(card)
    card_key = card_cfg.key
    total_len = len(df)

    if total_len == 0:
        empty_code = pd.Series(dtype="object")
        empty_desc = pd.Series(dtype="object")
        if return_pad_count:
            return empty_code, empty_desc, 0
        return empty_code, empty_desc

    mcc_code_list = []
    mcc_desc_list = []

    if card_key == "pinelabs":
        col = "mcc"
        series = df[col] if col in df.columns else pd.Series([None] * total_len, index=df.index)
        for val in series:
            if is_null_token(val):
                mcc_code_list.append("")
                mcc_desc_list.append("")
                continue
            s = str(val).strip()
            # Match leading 1-4 digits, optional delimiter and remainder description
            match = re.match(r"^(\d{1,4})(?:\s*-\s*|\s+|-)?(.*)$", s)
            if match:
                code = match.group(1)
                desc = match.group(2).strip()
                if desc in NULL_TOKENS:
                    desc = ""
                mcc_code_list.append(code)
                mcc_desc_list.append(desc)
            else:
                mcc_code_list.append("")
                mcc_desc_list.append("")

    elif card_key == "vegapay":
        code_col = "MCC"
        desc_col = "MCC Description"
        code_s = df[code_col] if code_col in df.columns else pd.Series([None] * total_len, index=df.index)
        desc_s = df[desc_col] if desc_col in df.columns else pd.Series([None] * total_len, index=df.index)
        for c_val, d_val in zip(code_s, desc_s):
            code = "" if is_null_token(c_val) else str(c_val).strip()
            desc = "" if is_null_token(d_val) else str(d_val).strip()
            mcc_code_list.append(code)
            mcc_desc_list.append(desc)

    elif card_key == "visa":
        code_col = "spmcat"
        code_s = df[code_col] if code_col in df.columns else pd.Series([None] * total_len, index=df.index)
        for c_val in code_s:
            code = "" if is_null_token(c_val) else str(c_val).strip()
            mcc_code_list.append(code)
            mcc_desc_list.append("")

    else:
        mcc_code_list = [""] * total_len
        mcc_desc_list = [""] * total_len

    # Optional zero-padding to 4 digits (defaults OFF, ON for PineLabs)
    pad_count = 0
    if card_cfg.pad_mcc_to_4:
        new_mcc_code_list = []
        for c in mcc_code_list:
            if c.isdigit() and len(c) < 4:
                new_mcc_code_list.append(c.zfill(4))
                pad_count += 1
            else:
                new_mcc_code_list.append(c)
        mcc_code_list = new_mcc_code_list

    s_code = pd.Series(mcc_code_list, index=df.index, name="mcc_code")
    s_desc = pd.Series(mcc_desc_list, index=df.index, name="mcc_description")
    if return_pad_count:
        return s_code, s_desc, pad_count
    return s_code, s_desc


def format_mcc_display(code: Any, description: Any) -> str:
    """Format MCC for display in filter lists: 'code - description' if description exists."""
    c = "" if is_null_token(code) else str(code).strip()
    d = "" if is_null_token(description) else str(description).strip()
    if not c:
        return ""
    if d:
        return f"{c} - {d}"
    return c


# --- Whitespace Normalization & Search Utilities ---

def collapse_whitespace(val: Any) -> str:
    """Normalize text by collapsing line breaks, tabs, and runs of spaces into a single space."""
    if val is None or pd.isna(val):
        return ""
    s = str(val).strip()
    if not s or s in NULL_TOKENS:
        return ""
    return re.sub(r"\s+", " ", s)


def search_dataframe(
    df: pd.DataFrame,
    query: str,
    columns: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Filter DataFrame rows matching search query whitespace-insensitively and case-insensitively.
    Collapses whitespace on both query and searched values.
    Raw DataFrame values are kept untouched for export.
    """
    clean_query = collapse_whitespace(query).lower()
    if not clean_query:
        return df

    if columns:
        search_cols = [c for c in columns if c in df.columns]
    else:
        search_cols = [
            c for c in df.columns
            if not c.startswith("_raw_")
            and not pd.api.types.is_numeric_dtype(df[c])
            and not pd.api.types.is_datetime64_any_dtype(df[c])
        ]

    mask = pd.Series(False, index=df.index)
    for col in search_cols:
        col_normalized = df[col].astype(str).apply(collapse_whitespace).str.lower()
        mask = mask | col_normalized.str.contains(clean_query, regex=False)

    return df[mask]


# --- Date Parsing & Diagnostics Utilities ---

def is_null_token(val: Any) -> bool:
    """Check if value is a known null/placeholder token or empty/whitespace."""
    if val is None or pd.isna(val):
        return True
    s = str(val).strip()
    return s in NULL_TOKENS


def get_shape(val: Any) -> str:
    """Mask a value to its shape: digits -> '9', letters -> 'A'.
    Empty strings, whitespace-only strings, None, and NaN return '<BLANK>'.
    Never leaks real cell values.
    """
    if val is None or pd.isna(val):
        return "<BLANK>"
    s = str(val).strip()
    if not s:
        return "<BLANK>"
    chars = []
    for ch in s:
        if ch.isdigit():
            chars.append("9")
        elif ch.isalpha():
            chars.append("A")
        else:
            chars.append(ch)
    return "".join(chars)


def parse_dates(
    series: pd.Series,
    config: Union[List[str], Dict[str, Any]],
    pad: Optional[int] = None
) -> pd.Series:
    """Parse dates using an ordered list of explicit formats.
    
    Supports optional left-padding (e.g. pad=8 for DDMMYYYY).
    Treats NULL_TOKENS as blank (NaT).
    Never guesses formats. Strips whitespace. Tries candidate formats
    in order only on rows not yet parsed.
    """
    if not isinstance(series, pd.Series):
        series = pd.Series(series)

    if isinstance(config, dict):
        formats = config.get("formats", [])
        if pad is None:
            pad = config.get("pad")
    else:
        formats = config

    result = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")

    # Identify non-null candidates
    cleaned = series.dropna().astype(str).str.strip()
    remaining = cleaned[~cleaned.isin(NULL_TOKENS)]

    if pad is not None and not remaining.empty:
        # Left-pad digits if shorter than expected width
        remaining = remaining.apply(
            lambda v: v.zfill(pad) if v.isdigit() and len(v) < pad else v
        )

    for fmt in formats:
        if remaining.empty:
            break
        parsed = pd.to_datetime(remaining, format=fmt, errors="coerce")
        success_mask = parsed.notna()
        if success_mask.any():
            matched_idx = remaining[success_mask].index
            result.loc[matched_idx] = parsed[success_mask]
            remaining = remaining[~success_mask]

    return result


def get_parse_failures(
    raw_series: pd.Series,
    parsed_series: pd.Series,
    col_name: str = ""
) -> Dict[str, Any]:
    """Identify genuine parse failures vs known placeholder blanks.
    
    Known NULL_TOKENS (like '-' or empty) are tracked as placeholder blanks
    without triggering parse-failure warnings.
    Unexpected shapes that failed to parse trigger a warning with shapes and counts.
    Never logs or returns real cell values.
    """
    if not isinstance(raw_series, pd.Series):
        raw_series = pd.Series(raw_series)
    if not isinstance(parsed_series, pd.Series):
        parsed_series = pd.Series(parsed_series)

    is_placeholder_mask = raw_series.apply(is_null_token)
    placeholder_count = int(is_placeholder_mask.sum())
    placeholder_shapes = Counter(get_shape(val) for val in raw_series[is_placeholder_mask])

    # Genuine failure: not a known placeholder, yet failed to parse into valid datetime
    failed_mask = (~is_placeholder_mask) & parsed_series.isna()
    failed_count = int(failed_mask.sum())
    failed_shapes = Counter(get_shape(val) for val in raw_series[failed_mask])
    top_3_failed = failed_shapes.most_common(3)

    if failed_count > 0:
        shapes_str = ", ".join(f"'{sh}' ({cnt})" for sh, cnt in top_3_failed)
        prefix = f"WARNING {col_name}: " if col_name else "WARNING: "
        warning_msg = f"{prefix}{failed_count} values could not be parsed, turned into blanks (shapes: {shapes_str})"
    else:
        warning_msg = ""

    if placeholder_count > 0:
        ph_str = ", ".join(f"'{sh}' ({cnt})" for sh, cnt in placeholder_shapes.most_common(3))
        prefix = f"INFO {col_name}: " if col_name else "INFO: "
        info_msg = f"{prefix}{placeholder_count} placeholder blanks ({ph_str})"
    else:
        info_msg = ""

    return {
        "failed_count": failed_count,
        "failed_shapes": top_3_failed,
        "warning_message": warning_msg,
        "placeholder_count": placeholder_count,
        "placeholder_shapes": dict(placeholder_shapes),
        "info_message": info_msg,
        "all_failed_shapes": dict(failed_shapes),
    }


def check_dob_data_quality(dob_series: pd.Series) -> Dict[str, Any]:
    """Check for default Unix epoch placeholders (1970-01-01) in DOB data."""
    if not isinstance(dob_series, pd.Series):
        dob_series = pd.Series(dob_series)
    epoch_mask = (dob_series == DEFAULT_EPOCH_DOB)
    count = int(epoch_mask.sum())
    msg = f"DATA QUALITY NOTE: {count} DOB values equal default epoch placeholder 1970-01-01" if count > 0 else ""
    return {
        "placeholder_dob_count": count,
        "note": msg
    }


__all__ = [
    "CARDS",
    "CardConfig",
    "DATE_CONFIGS",
    "NULL_TOKENS",
    "DEFAULT_EPOCH_DOB",
    "ISO_3166_1_ALPHA2",
    "ISO_3166_1_ALPHA3_TO_ALPHA2",
    "VISA_EXPECTED_COLUMNS",
    "PINELABS_EXPECTED_COLUMNS",
    "VEGAPAY_EXPECTED_COLUMNS",
    "get_card_config",
    "pad_column",
    "apply_column_padding",
    "validate_iso_country",
    "derive_country",
    "is_null_token",
    "get_shape",
    "parse_dates",
    "get_parse_failures",
    "check_dob_data_quality",
]
