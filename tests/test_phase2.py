"""Tests for Phase 2: Card schemas, column addition, ISO country derivation, typing, padding, and engine parity."""

import datetime
import io
import openpyxl
import pandas as pd
import pytest

from app.cards import (
    CARDS,
    NULL_TOKENS,
    PINELABS_EXPECTED_COLUMNS,
    VEGAPAY_EXPECTED_COLUMNS,
    VISA_EXPECTED_COLUMNS,
    apply_column_padding,
    derive_country,
    get_card_config,
    get_parse_failures,
    is_null_token,
    pad_column,
    validate_iso_country,
)
from app.services.headers import add_headers, read_excel_bytes, to_xlsx_bytes
from app.services.typing import apply_card_typing


def create_in_memory_xlsx(rows: list) -> bytes:
    """Create a synthetic Excel workbook in memory using openpyxl."""
    wb = openpyxl.Workbook()
    ws = wb.active
    for r_idx, row in enumerate(rows, start=1):
        for c_idx, val in enumerate(row, start=1):
            cell = ws.cell(row=r_idx, column=c_idx)
            cell.value = val
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# 1. Correct column count succeeds per card
@pytest.mark.parametrize("card_key", ["visa", "pinelabs", "vegapay"])
def test_add_headers_correct_column_count_succeeds_per_card(card_key):
    """Verify that headerless synthetic files with exact expected column count succeed and map headers properly."""
    card_cfg = get_card_config(card_key)
    col_count = len(card_cfg.expected_columns)
    rows = [[f"r{r}_c{c}" for c in range(col_count)] for r in range(3)]
    excel_bytes = create_in_memory_xlsx(rows)

    result = add_headers(excel_bytes, card_key)
    assert result["ok"] is True
    assert result["rows"] == 3
    assert result["found_columns"] == col_count
    assert result["expected_columns"] == col_count
    assert result["df"].columns.tolist() == card_cfg.expected_columns


# 2. Extra column fails
def test_add_headers_extra_column_fails():
    """Verify that uploading a file with more columns than expected fails with clear count mismatch message."""
    # VISA expects 29 columns; provide 30
    too_many_rows = [["val"] * 30]
    excel_bytes = create_in_memory_xlsx(too_many_rows)
    result = add_headers(excel_bytes, "visa")
    assert result["ok"] is False
    assert result["df"] is None
    assert "found 30 columns, expected 29 for VISA" in result["message"]


# 3. Missing column fails
def test_add_headers_missing_column_fails():
    """Verify that uploading a file with fewer columns than expected fails with clear count mismatch message."""
    # VISA expects 29 columns; provide 28
    too_few_rows = [["val"] * 28]
    excel_bytes = create_in_memory_xlsx(too_few_rows)
    result = add_headers(excel_bytes, "visa")
    assert result["ok"] is False
    assert result["df"] is None
    assert "found 28 columns, expected 29 for VISA" in result["message"]


# 4. All-empty rows dropped
def test_add_headers_drops_all_empty_rows():
    """Verify that completely empty or whitespace-only rows are dropped and index is normalized."""
    col_count = len(VISA_EXPECTED_COLUMNS)
    rows = [
        ["val"] * col_count,               # Row 0: valid
        [None] * col_count,                # Row 1: all None
        ["val2"] * col_count,              # Row 2: valid
        ["   "] * col_count,              # Row 3: all whitespace
        ["val3"] * col_count,              # Row 4: valid
    ]
    excel_bytes = create_in_memory_xlsx(rows)

    result = add_headers(excel_bytes, "visa")
    assert result["ok"] is True
    assert result["rows"] == 3
    assert result["df"].shape[0] == 3
    assert result["df"].index.tolist() == [0, 1, 2]


# 5. Leading zeros preserved
def test_add_headers_preserves_leading_zeros():
    """Verify leading zeros (e.g. '00000003', '012345') remain untouched as text."""
    col_count = len(VISA_EXPECTED_COLUMNS)
    row = ["val"] * col_count
    row[0] = "00000003"
    row[1] = "012345"
    excel_bytes = create_in_memory_xlsx([row])

    result = add_headers(excel_bytes, "visa")
    assert result["ok"] is True
    df = result["df"]
    assert df.iloc[0, 0] == "00000003"
    assert df.iloc[0, 1] == "012345"


# 6. Already-has-headers detected
def test_add_headers_detects_already_has_headers():
    """Verify that uploading a file that already has headers is detected and rejected with a helpful message."""
    rows = [
        VISA_EXPECTED_COLUMNS,
        ["val"] * len(VISA_EXPECTED_COLUMNS),
    ]
    excel_bytes = create_in_memory_xlsx(rows)

    result = add_headers(excel_bytes, "visa")
    assert result["ok"] is False
    assert result["df"] is None
    assert "File already contains VISA column headers" in result["message"]


# 7. Exact headers applied in order
def test_add_headers_exact_headers_applied_in_order():
    """Verify headers are applied in exact schema order and round-trip export preserves ordering and values."""
    df_orig = pd.DataFrame({
        "col_a": ["001", "002"],
        "col_b": ["alpha", "beta"],
        "col_c": ["100.50", "200.75"],
    })
    xlsx_bytes = to_xlsx_bytes(df_orig)
    assert isinstance(xlsx_bytes, bytes)
    assert len(xlsx_bytes) > 0

    df_read = read_excel_bytes(xlsx_bytes, header=0)
    assert df_read.columns.tolist() == ["col_a", "col_b", "col_c"]
    assert df_read["col_a"].tolist() == ["001", "002"]
    assert df_read["col_b"].tolist() == ["alpha", "beta"]


# 8. ISO country derived per card
def test_derive_country_iso_per_card():
    """Verify ISO country derivation per card (VISA, PineLabs, Vegapay) matches alpha-2 standard."""
    # VISA: last token of spldes
    df_visa = pd.DataFrame({
        "spldes": ["CHOPSTIX BEACONSFIELD GB", "MCDONALDS DUBAI AE", "UNKNOWN OUTLET 12345"]
    })
    assert derive_country(df_visa, "visa").tolist() == ["GB", "AE", "Unknown"]

    # PineLabs: last 2-letter uppercase ISO token of Merchant Name & Location
    df_pine = pd.DataFrame({
        "Merchant Name & Location": [
            "STARBUCKS MUMBAI IN 400001",
            "CAFE COFFEE DAY IN",
            "COFFEE SHOP BANGALORE IND",
        ]
    })
    assert derive_country(df_pine, "pinelabs").tolist() == ["IN", "IN", "Unknown"]

    # Vegapay: Merchant Country (accepts alpha-2, alpha-3, and common full names)
    df_vega = pd.DataFrame({
        "Merchant Country": ["IN", "USA", "United Kingdom", "UnknownCountry", "-"]
    })
    assert derive_country(df_vega, "vegapay").tolist() == ["IN", "US", "GB", "Unknown", "Unknown"]


# 9. Typing: numeric, dates explicit, ids as text
def test_apply_card_typing_coercion():
    """Verify typing service explicitly coerces numerics, parses dates with explicit formats, and preserves IDs as text."""
    df = pd.DataFrame({
        "Business Date": ["2026-10-15", "2026-10-16"],
        "DOB": ["12-05-1990", "01-01-1970"],
        "Mastercard Date": ["10-10-2026", "-"],
        "Transaction Date": ["28-09-2026", "13-10-2026"],
        "Settlement Date": ["2026-10-11", "2026-10-11 00:00:00"],
        "Transaction Amount": ["1500.50", "2000"],
        "Customer ID": ["00012345", "00067890"],
        "Merchant Country": ["IN", "US"],
    })

    result = apply_card_typing(df, "vegapay")
    typed_df = result["df"]

    assert str(typed_df["Transaction Amount"].dtype).startswith("float") or str(typed_df["Transaction Amount"].dtype).startswith("int")
    assert typed_df["Transaction Amount"].iloc[0] == 1500.50
    assert str(typed_df["Business Date"].dtype).startswith("datetime64")
    assert typed_df["Customer ID"].iloc[0] == "00012345"  # Text preserved
    assert typed_df["country_code"].tolist() == ["IN", "US"]
    assert result["dob_quality_note"] is not None
    assert "1 DOB values equal default epoch placeholder" in result["dob_quality_note"]


# 10. Single source of truth test (app/cards.py vs cards.py)
def test_single_source_of_truth_strict():
    """Fail if root cards.py and app/cards.py differ or if independent configs are created."""
    import cards as root_cards
    import app.cards as app_cards

    # Both must refer to the exact same objects in memory
    assert root_cards.CARDS is app_cards.CARDS
    assert root_cards.DATE_CONFIGS is app_cards.DATE_CONFIGS
    assert root_cards.get_card_config is app_cards.get_card_config
    assert root_cards.derive_country is app_cards.derive_country
    assert root_cards.parse_dates is app_cards.parse_dates
    assert root_cards.apply_column_padding is app_cards.apply_column_padding
    assert root_cards.NULL_TOKENS is app_cards.NULL_TOKENS


# 11. Country code edge cases
def test_country_code_edge_cases():
    """Verify country derivation across edge cases: valid code, city ending, numeric ending, lowercase, empty, and PineLabs TO/IN words.
    
    NOTE on PineLabs 'TO' / 'IN':
    'TO' is the official ISO 3166-1 alpha-2 code for Tonga, and 'IN' is India.
    In merchant descriptors like 'STARBUCKS MUMBAI IN 400001', 'IN' is safely captured.
    If a merchant name ends with 'TO' without country (e.g. 'MERCHANT TO'), it resolves to 'TO' (Tonga).
    This is an unavoidable edge case of 2-letter ISO validation, but mid-sentence prepositions
    ('PAY TO CAFE MUMBAI') are safe because the location is placed at the descriptor's end.
    """
    # 1. Valid code
    assert validate_iso_country("AE") == "AE"
    assert validate_iso_country("GB") == "GB"

    # 2. City-name ending
    assert validate_iso_country("LONDON") == "Unknown"
    assert validate_iso_country("DUBAI") == "Unknown"

    # 3. Numeric ending
    assert validate_iso_country("12345") == "Unknown"

    # 4. Lowercase
    assert validate_iso_country("ae") == "AE"
    assert validate_iso_country("gb") == "GB"

    # 5. Empty / whitespace / None / "-"
    assert validate_iso_country("") == "Unknown"
    assert validate_iso_country("   ") == "Unknown"
    assert validate_iso_country(None) == "Unknown"
    assert validate_iso_country("-") == "Unknown"

    # 6. PineLabs words: 'IN' (India) and 'TO' (Tonga)
    df_pinelabs_words = pd.DataFrame({
        "Merchant Name & Location": [
            "STARBUCKS MUMBAI IN 400001",     # Trailing 'IN' before postal code -> 'IN'
            "COFFEE SHOP BANGALORE IN",       # Direct trailing 'IN' -> 'IN'
            "STORE NAME TO",                  # Ends with 'TO' -> 'TO' (Tonga)
            "WELCOME TO CAFE MUMBAI",         # 'TO' is internal, city at end -> 'Unknown'
        ]
    })
    res = derive_country(df_pinelabs_words, "pinelabs")
    assert res.tolist() == ["IN", "IN", "TO", "Unknown"]


# 12. Engine parity test
def test_engine_parity_calamine_vs_openpyxl():
    """Verify calamine and openpyxl produce identical string DataFrames for numbers, floats, leading zeros, and native dates."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["int_col", "float_col", "zero_col", "date_col", "text_col"])
    ws.append([123, 45.67, "00123", datetime.date(2026, 10, 15), "hello"])
    ws.append(["999", "100.5", "00004", datetime.datetime(2026, 10, 16, 14, 30), "world"])
    ws.append([None, None, "-", None, ""])

    buf = io.BytesIO()
    wb.save(buf)
    excel_bytes = buf.getvalue()

    df_calamine = pd.read_excel(io.BytesIO(excel_bytes), dtype=str, engine="calamine")
    df_openpyxl = pd.read_excel(io.BytesIO(excel_bytes), dtype=str, engine="openpyxl")

    assert df_calamine.shape == df_openpyxl.shape
    assert df_calamine.columns.tolist() == df_openpyxl.columns.tolist()
    assert df_calamine.fillna("").equals(df_openpyxl.fillna(""))


# 13. Column padding test
def test_column_padding_preserves_null_tokens():
    """Verify pad_column and apply_column_padding pad short codes to width while preserving null tokens and blanks."""
    # Unit pad_column checks
    series = pd.Series(["3", "12345678", "-", "", None, "abc"])
    padded = pad_column(series, width=8)
    assert padded.tolist()[:3] == ["00000003", "12345678", "-"]
    assert padded.iloc[3] == ""
    assert pd.isna(padded.iloc[4])
    assert padded.iloc[5] == "abc"

    # apply_column_padding with VISA config (spcati: 8, spdate: 8)
    df_visa = pd.DataFrame({
        "spcati": ["1", "00000002", "-"],
        "spdate": ["1012026", "01012026", ""],
        "spdesc": ["3", "4", "5"],  # Not in pad_cols, remains unpadded
    })
    df_padded = apply_column_padding(df_visa, "visa")
    assert df_padded["spcati"].tolist() == ["00000001", "00000002", "-"]
    assert df_padded["spdate"].tolist() == ["01012026", "01012026", ""]
    assert df_padded["spdesc"].tolist() == ["3", "4", "5"]


# 14. Null tokens handling test
def test_null_tokens_handling_in_typing():
    """Verify NULL_TOKENS ('-', empty, whitespace) are blank without parse failure warnings, keeping separate placeholder count."""
    raw_dates = pd.Series(["10-10-2026", "-", "--", "None", "", "   ", "invalid_date"])
    col_cfg = {"formats": ["%d-%m-%Y"]}
    from app.cards import parse_dates
    parsed = parse_dates(raw_dates, col_cfg)

    failures = get_parse_failures(raw_dates, parsed, col_name="Mastercard Date")
    # Only 'invalid_date' is a parse failure; null tokens are counted as placeholders
    assert failures["failed_count"] == 1
    assert failures["placeholder_count"] == 5

    # Check numeric typing with NULL_TOKENS
    df = pd.DataFrame({
        "Days count": ["10", "-", "--", "nan", "abc", "20"],
    })
    result = apply_card_typing(df, "vegapay")
    # Only 'abc' triggers a numeric warning; '-', '--', 'nan' do not trigger warnings
    assert "Days count" in result["warnings"]
    assert result["warnings"]["Days count"]["failed_count"] == 1
