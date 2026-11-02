"""Type coercion and validation service for card analysis.

Reuses explicit date parsing and shape diagnostics from app.cards.
Never calls pd.to_datetime without an explicit format= argument.
Never touches disk or echoes real cell values in warnings.
"""

from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from app.cards import (
    CardConfig,
    apply_column_padding,
    check_dob_data_quality,
    derive_country,
    get_card_config,
    get_parse_failures,
    get_shape,
    is_null_token,
    parse_dates,
)


def apply_card_typing(
    df: pd.DataFrame,
    card: Union[str, CardConfig, Dict[str, Any]],
) -> Dict[str, Any]:
    """Coerce DataFrame columns into explicit types according to card configuration.

    Rules:
    - Numeric columns converted with pd.to_numeric(errors="coerce").
    - Date columns parsed with explicit ordered candidate formats (parse_dates).
    - ID-like columns preserved strictly as text.
    - Derived 'country_code' column added.
    - Preserves a string label view for UI matching and search.
    - Tracks per-column parse warnings with structural shapes (no raw data leaked).
    """
    card_cfg = get_card_config(card)
    # Apply column padding in the Analysis typing path only
    # Preserves untouched originals in _raw_<col> and tracks counts
    typed_df, padded_counts = apply_column_padding(df.copy(), card_cfg)
    padding_notes = [
        f"{count} values zero-padded in {col}"
        for col, count in padded_counts.items()
        if count > 0
    ]

    # Track warnings and diagnostic reports
    warnings: Dict[str, Any] = {}
    date_ranges: Dict[str, Any] = {}
    dob_quality_note = None

    # 1. Coerce numeric columns
    for col in card_cfg.numeric_cols:
        if col in typed_df.columns:
            raw_col = typed_df[col]
            numeric_col = pd.to_numeric(raw_col, errors="coerce")
            # Count invalid non-numeric entries (excluding known null tokens)
            invalid_mask = numeric_col.isna() & raw_col.notna() & (~raw_col.apply(is_null_token))
            invalid_count = int(invalid_mask.sum())
            if invalid_count > 0:
                shapes = [get_shape(v) for v in raw_col[invalid_mask][:3]]
                warnings[col] = {
                    "failed_count": invalid_count,
                    "shapes": shapes,
                    "message": f"WARNING {col}: {invalid_count} non-numeric values turned into blanks",
                }
            typed_df[col] = numeric_col

    # 2. Coerce date columns using explicit formats (never format-guessing)
    for col, col_cfg in card_cfg.date_cols.items():
        if col in typed_df.columns:
            raw_col = typed_df[col]
            parsed_col = parse_dates(raw_col, col_cfg)
            failures = get_parse_failures(raw_col, parsed_col, col_name=col)
            if failures["failed_count"] > 0:
                warnings[col] = {
                    "failed_count": failures["failed_count"],
                    "shapes": failures["failed_shapes"],
                    "message": failures["warning_message"],
                }
            typed_df[col] = parsed_col

            # Min/max date boundaries
            valid_dates = parsed_col.dropna()
            if not valid_dates.empty:
                date_ranges[col] = {
                    "min": valid_dates.min().strftime("%Y-%m-%d"),
                    "max": valid_dates.max().strftime("%Y-%m-%d"),
                }
            else:
                date_ranges[col] = {"min": None, "max": None}

            # Special check for DOB placeholder 1970-01-01
            if col == "DOB":
                dob_check = check_dob_data_quality(parsed_col)
                if dob_check["placeholder_dob_count"] > 0:
                    dob_quality_note = dob_check["note"]

    # 3. Ensure ID-like columns remain text
    for col in card_cfg.id_like_cols:
        if col in typed_df.columns:
            typed_df[col] = typed_df[col].fillna("").astype(str)

    # 4. Derive country_code column
    typed_df["country_code"] = derive_country(typed_df, card_cfg)

    # 5. Extract per-column metadata
    total_rows = len(typed_df)
    columns_info: List[Dict[str, Any]] = []

    for col in typed_df.columns:
        if col.startswith("_raw_"):
            continue
        series = typed_df[col]
        null_count = int(series.isna().sum())
        null_pct = round((null_count / total_rows * 100), 2) if total_rows > 0 else 0.0
        unique_count = int(series.nunique(dropna=True))

        if col in card_cfg.numeric_cols:
            col_type = "number"
        elif col in card_cfg.date_cols:
            col_type = "date"
        else:
            col_type = "text"

        columns_info.append({
            "name": col,
            "type": col_type,
            "null_pct": null_pct,
            "unique_count": unique_count,
            "is_key": col in card_cfg.key_cols or col == "country_code",
            "is_sensitive": col in card_cfg.sensitive_cols,
        })

    return {
        "df": typed_df,
        "rows": total_rows,
        "columns_info": columns_info,
        "warnings": warnings,
        "date_ranges": date_ranges,
        "dob_quality_note": dob_quality_note,
        "padded_counts": padded_counts,
        "padding_notes": padding_notes,
        "country_confidence": card_cfg.country_confidence,
    }

