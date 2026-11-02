"""Card configurations and explicit date parsing utilities for CardLyze.

Provides shared date parsing functions that:
1. Strip whitespace.
2. Support optional per-column left-padding (e.g. zfill(8) for DDMMYYYY).
3. Try explicit candidate formats in order only on unparsed rows.
4. Never guess date formats.
5. Filter known placeholder tokens (NULL_TOKENS) as blanks without warning.
6. Warn only for unexpected shapes, and track informational placeholder counts.
"""

from collections import Counter
from typing import Any, Dict, List, Optional, Union
import pandas as pd

NULL_TOKENS = frozenset({"-", "--", "---", "", "None", "none", "nan", "NaN", "NAT", "NaT", "null", "NULL"})
DEFAULT_EPOCH_DOB = pd.Timestamp("1970-01-01")

DATE_CONFIGS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "Vegapay": {
        "Business Date": {"formats": ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S"]},
        "DOB": {"formats": ["%d-%m-%Y", "%d-%m-%Y %H:%M:%S"]},
        "Mastercard Date": {"formats": ["%d-%m-%Y", "%d-%m-%Y %H:%M:%S"]},
        "Transaction Date": {"formats": ["%d-%m-%Y", "%d-%m-%Y %H:%M:%S"]},
        "Settlement Date": {"formats": ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S"]},
    },
    "PineLabs": {
        "Value Date": {"formats": ["%d/%m/%Y %H:%M:%S", "%d/%m/%Y"]},
        "Transaction Date": {"formats": ["%d/%m/%Y %H:%M:%S", "%d/%m/%Y"]},
    },
    "VISA": {
        "spbusd": {"formats": ["%Y-%m-%d"]},
        "spdate": {"formats": ["%d%m%Y"], "pad": 8},
    },
}

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
