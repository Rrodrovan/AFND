from datetime import date

from src.process.drought import longest_dry_spell, monthly_totals


def test_longest_dry_spell_counts_consecutive_dry_days():
    assert longest_dry_spell([0, 0, 5, 0, 0, 0, 2]) == 3


def test_missing_data_breaks_the_spell():
    assert longest_dry_spell([0, 0, None, 0, 0]) == 2


def test_no_dry_days():
    assert longest_dry_spell([5, 6, 7]) == 0


def test_threshold_is_respected():
    assert longest_dry_spell([0.5, 0.9, 1.0, 0.2], threshold_mm=1.0) == 2


def test_monthly_totals_ignores_missing_values():
    rows = [
        {"date": date(2020, 6, 1), "precip_mm": 10.0},
        {"date": date(2020, 6, 2), "precip_mm": None},
        {"date": date(2020, 6, 3), "precip_mm": 5.5},
        {"date": date(2020, 7, 1), "precip_mm": 2.0},
    ]
    assert monthly_totals(rows) == {"2020-06": 15.5, "2020-07": 2.0}
