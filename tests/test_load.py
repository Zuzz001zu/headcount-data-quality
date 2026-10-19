import pandas as pd
import pytest

from headcount.load import load_sources, parse_dates, parse_number
from tests.conftest import PERIOD, employee, make_sources, pay


def test_parse_dates_accepts_the_formats_found_in_exports():
    parsed = parse_dates(pd.Series(["31.12.2020", "2021-02-03", "05/06/2019", " 01.01.2000 "]))
    assert parsed.dt.strftime("%Y-%m-%d").tolist() == [
        "2020-12-31",
        "2021-02-03",
        "2019-06-05",
        "2000-01-01",
    ]


def test_parse_dates_returns_nat_for_impossible_dates():
    parsed = parse_dates(pd.Series(["31.02.2020", "2019-13-01", "n/a", "", None]))
    assert parsed.isna().all()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("80", 80.0), ("80 %", 80.0), ("50,5", 50.5), ("6'450.50", 6450.5), ("12 000", 12000.0)],
)
def test_parse_number(raw, expected):
    assert parse_number(pd.Series([raw])).iloc[0] == expected


def test_parse_number_returns_nan_for_text():
    assert parse_number(pd.Series(["abc", "", None])).isna().all()


def test_employees_are_normalized():
    sources = make_sources(
        [employee("e10001", nom="  FAVRE ", sexe=" f", unite="fin-cpt", no_avs="7569217076985")],
        [pay("E10001")],
    )
    row = sources.employees.iloc[0]
    assert row["employee_id"] == "E10001"
    assert row["last_name"] == "Favre"
    assert row["gender"] == "F"
    assert row["unit_code"] == "FIN-CPT"
    assert row["avs"] == "756.9217.0769.85"
    assert pd.isna(row["exit_date"])


def test_raw_date_is_kept_for_reporting():
    sources = make_sources([employee("E10001", date_entree="2019-13-01")], [pay("E10001")])
    row = sources.employees.iloc[0]
    assert pd.isna(row["hire_date"])
    assert row["hire_date_raw"] == "2019-13-01"


def test_reference_date_is_last_day_of_period():
    sources = make_sources([employee("E10001")], [pay("E10001")])
    assert sources.period_start == pd.Timestamp("2026-09-01")
    assert sources.reference_date == pd.Timestamp("2026-09-30")


def test_missing_payroll_file_is_reported(tmp_path):
    with pytest.raises(FileNotFoundError, match="2026-09"):
        load_sources(tmp_path, PERIOD)
