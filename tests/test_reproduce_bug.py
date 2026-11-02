import pandas as pd
import pytest

def naive_parse_dates(series: pd.Series) -> pd.Series:
    """The buggy format-guessing parser previously used in the notebook."""
    return pd.to_datetime(series, errors="coerce")

@pytest.mark.xfail(strict=True, reason="Naive format-guessing parser swaps day and month (03-04 becomes March 4 instead of April 3)")
def test_reproduce_day_month_swap_naive():
    """(a) 03-04-2026 must parse as 3 April 2026; naive parser swaps day and month to March 4."""
    s = pd.Series(["03-04-2026"])
    parsed = naive_parse_dates(s)
    assert parsed.iloc[0] == pd.Timestamp("2026-04-03")

@pytest.mark.xfail(strict=True, reason="Naive format-guessing parser fails on day > 12 when first value is ambiguous")
def test_reproduce_ambiguous_first_value_naive():
    """(b) Column starting with 10-10-2026 followed by 28-09-2026 and 13-10-2026 must parse all three."""
    s = pd.Series(["10-10-2026", "28-09-2026", "13-10-2026"])
    parsed = naive_parse_dates(s)
    assert parsed.notna().all()
    assert parsed.iloc[0] == pd.Timestamp("2026-10-10")
    assert parsed.iloc[1] == pd.Timestamp("2026-09-28")
    assert parsed.iloc[2] == pd.Timestamp("2026-10-13")

@pytest.mark.xfail(strict=True, reason="Naive format-guessing parser fails on second shape in mixed ISO date and datetime")
def test_reproduce_mixed_shapes_settlement_date_naive():
    """(c) Settlement Date column mixing '2026-10-11' and '2026-10-11 00:00:00' must parse both."""
    s = pd.Series(["2026-10-11", "2026-10-11 00:00:00"])
    parsed = naive_parse_dates(s)
    assert parsed.notna().all()
    assert parsed.iloc[0] == pd.Timestamp("2026-10-11")
    assert parsed.iloc[1] == pd.Timestamp("2026-10-11")
