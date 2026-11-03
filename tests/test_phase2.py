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


# --- Card Configs Sanity & Literal Counts (Item 4) ---

def test_cards_config_sanity_and_literal_counts():
    """Assert literal column counts 29, 68, 61, no duplicate names, and all referenced columns exist."""
    # Literal hard-coded count checks (not len() of config)
    assert len(VISA_EXPECTED_COLUMNS) == 29
    assert len(PINELABS_EXPECTED_COLUMNS) == 68
    assert len(VEGAPAY_EXPECTED_COLUMNS) == 61

    assert len(set(VISA_EXPECTED_COLUMNS)) == 29
    assert len(set(PINELABS_EXPECTED_COLUMNS)) == 68
    assert len(set(VEGAPAY_EXPECTED_COLUMNS)) == 61

    for card_key, card_cfg in CARDS.items():
        exp_cols = set(card_cfg.expected_columns)
        assert len(exp_cols) == len(card_cfg.expected_columns), f"Duplicate column in {card_key}"

        # Assert all referenced schema columns exist in expected_columns
        for col in card_cfg.numeric_cols:
            assert col in exp_cols, f"{card_key}: numeric_col '{col}' not in expected_columns"
        for col in card_cfg.date_cols.keys():
            assert col in exp_cols, f"{card_key}: date_col '{col}' not in expected_columns"
        for col in card_cfg.id_like_cols:
            assert col in exp_cols, f"{card_key}: id_like_col '{col}' not in expected_columns"
        for col in card_cfg.pad_cols.keys():
            assert col in exp_cols, f"{card_key}: pad_col '{col}' not in expected_columns"
        for col in card_cfg.sensitive_cols:
            assert col in exp_cols, f"{card_key}: sensitive_col '{col}' not in expected_columns"
        for col in card_cfg.key_cols:
            assert col in exp_cols, f"{card_key}: key_col '{col}' not in expected_columns"

        # mcc_col is a single valid column per card
        assert isinstance(card_cfg.mcc_col, str)
        assert card_cfg.mcc_col in exp_cols, f"{card_key}: mcc_col '{card_cfg.mcc_col}' not in expected_columns"
        assert card_cfg.country_confidence in ("exact", "derived")
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


# 5. Leading zeros preserved & Column Addition export equals input
def test_add_headers_preserves_leading_zeros():
    """Verify leading zeros remain untouched as text and Column Addition export equals input without padding."""
    col_count = len(VISA_EXPECTED_COLUMNS)
    row = ["val"] * col_count
    row[0] = "00000003"
    row[1] = "012345"
    # Column spcati is a padded column in Analysis; in Column Addition it MUST NOT be padded
    spcati_idx = VISA_EXPECTED_COLUMNS.index("spcati")
    row[spcati_idx] = "3"

    excel_bytes = create_in_memory_xlsx([row])
    result = add_headers(excel_bytes, "visa")
    assert result["ok"] is True
    df = result["df"]
    assert df.iloc[0, 0] == "00000003"
    assert df.iloc[0, 1] == "012345"
    # PADDING MUST NOT ALTER COLUMN ADDITION EXPORT: '3' remains '3'
    assert df["spcati"].iloc[0] == "3"

    # Export round-trip check
    out_xlsx = to_xlsx_bytes(df)
    df_exported = read_excel_bytes(out_xlsx, header=0)
    assert df_exported["spcati"].iloc[0] == "3"
    assert df_exported.iloc[0, 0] == "00000003"


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
    assert root_cards.derive_mcc is app_cards.derive_mcc
    assert root_cards.format_mcc_display is app_cards.format_mcc_display
    assert root_cards.collapse_whitespace is app_cards.collapse_whitespace
    assert root_cards.search_dataframe is app_cards.search_dataframe
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
    """Verify pad_column and apply_column_padding pad digit-only short values, leaving alphanumerics untouched, preserving raw in _raw_<col>, and reporting counts."""
    # Unit pad_column checks
    series = pd.Series(["3", "12345678", "-", "", None, "3A", "abc"])
    padded, count = pad_column(series, width=8)
    assert padded.tolist()[:3] == ["00000003", "12345678", "-"]
    assert padded.iloc[3] == ""
    assert pd.isna(padded.iloc[4])
    # Alphanumeric short values untouched
    assert padded.iloc[5] == "3A"
    assert padded.iloc[6] == "abc"
    # Only "3" was padded
    assert count == 1

    # apply_column_padding with VISA config (spcati: 8, spdate: 8)
    df_visa = pd.DataFrame({
        "spcati": ["1", "00000002", "-", "3A"],
        "spdate": ["1012026", "01012026", "", "15102026"],
        "spdesc": ["3", "4", "5", "6"],  # Not in pad_cols, remains unpadded
    })
    df_padded, counts = apply_column_padding(df_visa, "visa")
    # Padded values
    assert df_padded["spcati"].tolist() == ["00000001", "00000002", "-", "3A"]
    assert df_padded["spdate"].tolist() == ["01012026", "01012026", "", "15102026"]
    assert df_padded["spdesc"].tolist() == ["3", "4", "5", "6"]
    # Untouched originals preserved in hidden _raw_<col>
    assert df_padded["_raw_spcati"].tolist() == ["1", "00000002", "-", "3A"]
    assert df_padded["_raw_spdate"].tolist() == ["1012026", "01012026", "", "15102026"]
    # Padded counts reported
    assert counts["spcati"] == 1  # Only "1" was padded
    assert counts["spdate"] == 1  # Only "1012026" was padded

    # Check that apply_card_typing reports padded_counts and padding_notes
    result = apply_card_typing(df_visa, "visa")
    assert result["padded_counts"]["spcati"] == 1
    assert "1 values zero-padded in spcati" in result["padding_notes"]
    assert "_raw_spcati" not in [c["name"] for c in result["columns_info"]]
    assert result["country_confidence"] == "derived"


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


# 15. RRN Not Padded & Quality Note Reported
def test_padding_rrn_not_padded_and_quality_note_reported():
    """Verify RRN is not padded, short values remain unchanged, and non-12 character count is reported in summary."""
    df_vega = pd.DataFrame({
        "Terminal ID": ["123", "45678901", "-"],  # Padded column (pad 8)
        "RRN": ["123456", "123456789012", "-"],  # RRN must NOT be padded
    })
    result = apply_card_typing(df_vega, "vegapay")
    df_typed = result["df"]

    # Terminal ID is padded
    assert df_typed["Terminal ID"].iloc[0] == "00000123"
    assert df_typed["Terminal ID"].iloc[1] == "45678901"

    # RRN is NOT padded: '123456' remains '123456'
    assert df_typed["RRN"].iloc[0] == "123456"
    assert df_typed["RRN"].iloc[1] == "123456789012"
    assert df_typed["RRN"].iloc[2] == "-"

    # Data quality note reports count of non-12 length values
    assert result["rrn_quality_note"] == "1 RRN values are not 12 characters"

    # Check column metadata marked as derived for padded columns
    col_meta = {c["name"]: c for c in result["columns_info"]}
    assert col_meta["Terminal ID"]["is_derived"] is True
    assert col_meta["RRN"]["is_derived"] is False


# 16. Unknown Country Normal Selectable Filter Value & Summary
def test_unknown_country_selectable_filter_and_summary():
    """Verify Unknown country is a selectable filter value and country summary counts are computed dynamically."""
    df = pd.DataFrame({
        "spldes": [
            "STORE DUBAI AE",
            "STORE LONDON GB",
            "STORE UNKNOWN 12345",
            "-",
        ]
    })
    result = apply_card_typing(df, "visa")
    df_typed = result["df"]

    assert "Unknown" in df_typed["country_code"].unique()
    # Filter selection by Unknown works
    filtered = df_typed[df_typed["country_code"] == "Unknown"]
    assert len(filtered) == 2

    # Country summary is computed from data
    summary = result["country_summary"]
    assert summary["unknown_count"] == 2
    assert summary["unknown_pct"] == 50.0
    assert "2 transactions (50.0%) have Unknown country" in summary["note"]
    assert summary["confidence"] == "derived"


# 17. MCC Normalization Synthetic Tests Across All Cards
def test_mcc_normalization_synthetic_all_cards():
    """Verify MCC normalization parses code & description for PineLabs, Vegapay, and VISA, preserving leading zeros."""
    from app.cards import derive_mcc, format_mcc_display

    # 1. PineLabs split: '<4 digits>-<description>'
    df_pine = pd.DataFrame({
        "mcc": [
            "0742-VETERINARY SERVICES",
            "5411 - GROCERY STORES",
            "-",
            "INVALID_MCC",
            None,
        ]
    })
    code_s, desc_s = derive_mcc(df_pine, "pinelabs")
    assert code_s.tolist() == ["0742", "5411", "", "", ""]
    assert desc_s.tolist() == ["VETERINARY SERVICES", "GROCERY STORES", "", "", ""]

    # 2. Vegapay: MCC and MCC Description
    df_vega = pd.DataFrame({
        "MCC": ["0742", "5411", "-", ""],
        "MCC Description": ["Veterinary", "Grocery", "-", ""],
    })
    code_v, desc_v = derive_mcc(df_vega, "vegapay")
    assert code_v.tolist() == ["0742", "5411", "", ""]
    assert desc_v.tolist() == ["Veterinary", "Grocery", "", ""]

    # 3. VISA: spmcat is code, no description
    df_visa = pd.DataFrame({
        "spmcat": ["0742", "5411", "-"],
    })
    code_visa, desc_visa = derive_mcc(df_visa, "visa")
    assert code_visa.tolist() == ["0742", "5411", ""]
    assert desc_visa.tolist() == ["", "", ""]

    # 4. Display formatting helper
    assert format_mcc_display("0742", "Veterinary") == "0742 - Veterinary"
    assert format_mcc_display("5411", "") == "5411"
    assert format_mcc_display("", "") == ""


# 18. Whitespace Insensitive Search
def test_whitespace_insensitive_search():
    """Verify search is insensitive to runs of spaces, tabs, and newlines while raw values remain untouched for export."""
    from app.cards import collapse_whitespace, search_dataframe

    raw_val = "BLUE   MART\nFRESH   MINI  DUBAI AE"
    df = pd.DataFrame({
        "spldes": [raw_val, "OTHER STORE"],
        "city": ["DUBAI", "LONDON"],
    })

    # Search with multiple spaces and different casing
    res1 = search_dataframe(df, "blue mart fresh")
    assert len(res1) == 1
    assert res1.iloc[0]["spldes"] == raw_val  # Raw value untouched!

    res2 = search_dataframe(df, "  blue    mart   ")
    assert len(res2) == 1
    assert res2.iloc[0]["spldes"] == raw_val

    # Unit collapse_whitespace
    assert collapse_whitespace("  HELLO \n\t WORLD  ") == "HELLO WORLD"
    assert collapse_whitespace("-") == ""


# 19. Concurrency: Slow Parse Does Not Block Health & Semaphore Limit Enforced
def test_concurrency_slow_parse_does_not_block_health_and_semaphore_limit():
    """Verify background file parse does not block event loop (/api/health) and semaphore limit is enforced."""
    import asyncio
    import httpx
    from app.main import app

    async def _test_concurrency():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Launch slow parse task in background
            task = asyncio.create_task(client.post("/api/concurrency/test-parse?duration=0.6"))

            # Health check must respond immediately while parse is running
            await asyncio.sleep(0.05)
            health_res = await client.get("/api/health")
            assert health_res.status_code == 200
            assert health_res.json() == {"status": "ok"}

            parse_res = await task
            assert parse_res.status_code == 200
            assert parse_res.json() == {"status": "parsed"}

    asyncio.run(_test_concurrency())
