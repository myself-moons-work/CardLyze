import os
import re
import pandas as pd
import pytest
from cards import (
    parse_dates,
    get_shape,
    get_parse_failures,
    check_dob_data_quality,
    DATE_CONFIGS,
    NULL_TOKENS,
    DEFAULT_EPOCH_DOB,
)

def test_dd_mm_swap_case():
    """(a) 03-04-2026 must parse as 3 April 2026, never swapped to 4 March."""
    s = pd.Series(["03-04-2026"])
    parsed = parse_dates(s, ["%d-%m-%Y", "%d-%m-%Y %H:%M:%S"])
    assert parsed.iloc[0] == pd.Timestamp("2026-04-03")
    assert parsed.iloc[0].day == 3
    assert parsed.iloc[0].month == 4

def test_ambiguous_first_value_case():
    """(b) A column starting with 10-10-2026 followed by 28-09-2026 and 13-10-2026 must parse all three."""
    s = pd.Series(["10-10-2026", "28-09-2026", "13-10-2026"])
    parsed = parse_dates(s, ["%d-%m-%Y", "%d-%m-%Y %H:%M:%S"])
    assert parsed.notna().all()
    assert parsed.iloc[0] == pd.Timestamp("2026-10-10")
    assert parsed.iloc[1] == pd.Timestamp("2026-09-28")
    assert parsed.iloc[2] == pd.Timestamp("2026-10-13")

def test_mixed_iso_date_and_datetime_shapes():
    """(c) Mixed ISO date '2026-10-11' and datetime '2026-10-11 00:00:00' must parse both."""
    s = pd.Series(["2026-10-11", "2026-10-11 00:00:00"])
    parsed = parse_dates(s, ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S"])
    assert parsed.notna().all()
    assert parsed.iloc[0] == pd.Timestamp("2026-10-11")
    assert parsed.iloc[1] == pd.Timestamp("2026-10-11")

def test_whitespace_handling():
    """Whitespace is stripped from candidate date values before parsing."""
    s = pd.Series(["  2026-10-11  ", "\t10-10-2026\n"])
    parsed = parse_dates(s, ["%Y-%m-%d", "%d-%m-%Y"])
    assert parsed.notna().all()
    assert parsed.iloc[0] == pd.Timestamp("2026-10-11")
    assert parsed.iloc[1] == pd.Timestamp("2026-10-10")

def test_visa_spdate_left_padding():
    """VISA spdate: 7-digit strings missing leading zero must be left-padded with zfill(8).
    
    1012026 -> 01012026 (1 Jan 2026, NOT 10 Jan)
    2092026 -> 02092026 (2 Sep 2026, NOT 20 Sep)
    01012026 -> 01012026 (1 Jan 2026)
    """
    visa_spdate_cfg = DATE_CONFIGS["VISA"]["spdate"]
    s = pd.Series(["1012026", "2092026", "01012026"])
    parsed = parse_dates(s, visa_spdate_cfg)
    
    assert parsed.notna().all()
    # 1012026 -> 01/01/2026
    assert parsed.iloc[0] == pd.Timestamp("2026-01-01")
    assert parsed.iloc[0].day == 1
    assert parsed.iloc[0].month == 1
    
    # 2092026 -> 02/09/2026
    assert parsed.iloc[1] == pd.Timestamp("2026-09-02")
    assert parsed.iloc[1].day == 2
    assert parsed.iloc[1].month == 9

    # 01012026 -> 01/01/2026
    assert parsed.iloc[2] == pd.Timestamp("2026-01-01")
    assert parsed.iloc[2].day == 1
    assert parsed.iloc[2].month == 1

def test_known_placeholders_null_tokens_not_counted_as_failures():
    """Known placeholders in NULL_TOKENS (like '-' and whitespace) stay blank (NaT)
    without triggering parse failure warnings. Warn only for unexpected shapes.
    """
    s = pd.Series(["2026-10-11", "-", "", "   ", None, pd.NA, "invalid_date_shape"])
    parsed = parse_dates(s, ["%Y-%m-%d"])
    
    # Only index 0 parsed
    assert parsed.iloc[0] == pd.Timestamp("2026-10-11")
    assert parsed.iloc[1:].isna().all()

    report = get_parse_failures(s, parsed, col_name="Test Col")
    # 5 placeholder tokens ('-', '', '   ', None, pd.NA)
    assert report["placeholder_count"] == 5
    # Only 1 unexpected parse failure ('invalid_date_shape')
    assert report["failed_count"] == 1
    assert "WARNING Test Col: 1 values could not be parsed" in report["warning_message"]
    assert "INFO Test Col: 5 placeholder blanks" in report["info_message"]

def test_single_source_of_truth_cards_config():
    """cards.py at repo root and app/cards.py must share the exact same configs and functions."""
    import cards as root_cards
    import app.cards as app_cards

    assert root_cards.DATE_CONFIGS == app_cards.DATE_CONFIGS
    assert root_cards.NULL_TOKENS == app_cards.NULL_TOKENS
    assert root_cards.DEFAULT_EPOCH_DOB == app_cards.DEFAULT_EPOCH_DOB
    assert root_cards.parse_dates is app_cards.parse_dates
    assert root_cards.get_shape is app_cards.get_shape
    assert root_cards.get_parse_failures is app_cards.get_parse_failures
    assert root_cards.check_dob_data_quality is app_cards.check_dob_data_quality

def test_dob_data_quality_check():
    """DOB data quality check flags 1970-01-01 epoch placeholder dates."""
    s = pd.Series([pd.Timestamp("1970-01-01"), pd.Timestamp("1995-04-12"), pd.Timestamp("1970-01-01")])
    rep = check_dob_data_quality(s)
    assert rep["placeholder_dob_count"] == 2
    assert "2 DOB values equal default epoch placeholder 1970-01-01" in rep["note"]

def test_all_cards_have_explicit_format_list():
    """Every date column of all three cards has an explicit format list in the config."""
    expected_cards = {
        "Vegapay": [
            "Business Date", "DOB", "Mastercard Date", "Transaction Date", "Settlement Date"
        ],
        "PineLabs": [
            "Value Date", "Transaction Date"
        ],
        "VISA": [
            "spbusd", "spdate"
        ]
    }

    assert set(DATE_CONFIGS.keys()) == set(expected_cards.keys())

    for card_name, expected_cols in expected_cards.items():
        card_cfg = DATE_CONFIGS[card_name]
        assert set(card_cfg.keys()) == set(expected_cols)
        for col, col_cfg in card_cfg.items():
            formats = col_cfg["formats"] if isinstance(col_cfg, dict) else col_cfg
            assert isinstance(formats, list), f"{card_name}.{col} format must be a list"
            assert len(formats) > 0, f"{card_name}.{col} format list cannot be empty"
            for fmt in formats:
                assert "%" in fmt, f"Invalid format string {fmt} in {card_name}.{col}"

def test_no_call_to_pd_to_datetime_without_format():
    """Assert that no call to pd.to_datetime without a format= argument exists anywhere in the codebase."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    exclude_dirs = {".git", ".venv", "__pycache__", "scratch"}

    violations = []

    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if not (file.endswith(".py") or file.endswith(".ipynb")):
                continue
            if "test_reproduce_bug" in file:
                continue

            file_path = os.path.join(root, file)
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if file.endswith(".ipynb"):
                import json
                try:
                    nb = json.loads(content)
                    code_lines = []
                    for cell in nb.get("cells", []):
                        if cell.get("cell_type") == "code":
                            code_lines.extend(cell.get("source", []))
                    text_to_search = "".join(code_lines)
                except Exception:
                    text_to_search = content
            else:
                text_to_search = content

            for match in re.finditer(r"pd\.to_datetime\s*\(", text_to_search):
                start = match.end()
                depth = 1
                i = start
                while i < len(text_to_search) and depth > 0:
                    if text_to_search[i] == "(":
                        depth += 1
                    elif text_to_search[i] == ")":
                        depth -= 1
                    i += 1
                call_args = text_to_search[start:i-1]
                if "format=" not in call_args:
                    rel_path = os.path.relpath(file_path, root_dir)
                    violations.append((rel_path, match.group(0) + call_args + ")"))

    assert not violations, f"Found pd.to_datetime calls without format= argument: {violations}"

# Real file test marked with @pytest.mark.real_data so it is not part of default pytest run
REAL_VEGAPAY_PATH = r"data_with_headers\vegapay_with_headers_20261028.xlsx"

@pytest.mark.real_data
@pytest.mark.skipif(not os.path.exists(REAL_VEGAPAY_PATH), reason="Real data file not present")
def test_real_vegapay_dates_when_file_present():
    """Optional test on local real Vegapay file: verifies 0 parse failures, 90 epoch DOBs, and correct date ranges."""
    df = pd.read_excel(REAL_VEGAPAY_PATH, dtype=str)
    for col, cfg in DATE_CONFIGS["Vegapay"].items():
        conv = parse_dates(df[col], cfg)
        rep = get_parse_failures(df[col], conv, col_name=col)
        assert rep["failed_count"] == 0, f"Unexpected failures in {col}: {rep['warning_message']}"
    
    dob_check = check_dob_data_quality(parse_dates(df["DOB"], DATE_CONFIGS["Vegapay"]["DOB"]))
    assert dob_check["placeholder_dob_count"] == 90
