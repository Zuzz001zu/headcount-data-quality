"""Load the validated data into SQLite and run the statistics queries.

The queries live in headcount/sql/ so they can be read and reused on their own.
"""

from __future__ import annotations

import sqlite3
from importlib import resources

import pandas as pd

from headcount.load import Sources
from headcount.rules import payroll_in_period

EMPLOYEE_FIELDS = [
    "employee_id",
    "last_name",
    "first_name",
    "gender",
    "birth_date",
    "unit_code",
    "hire_date",
    "exit_date",
    "contract_type",
]


def read_query(name: str) -> str:
    return resources.files("headcount").joinpath("sql", f"{name}.sql").read_text(encoding="utf-8")


def _iso_dates(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    df = df.copy()
    for column in columns:
        df[column] = df[column].dt.strftime("%Y-%m-%d")
    return df


def build_database(sources: Sources, excluded: set[str]) -> sqlite3.Connection:
    employees = sources.employees[~sources.employees["employee_id"].isin(excluded)]
    employees = employees.dropna(subset=["employee_id"])[EMPLOYEE_FIELDS]
    payroll = payroll_in_period(sources)
    payroll = payroll[payroll["employee_id"].isin(employees["employee_id"])]

    con = sqlite3.connect(":memory:")
    _iso_dates(employees, ["birth_date", "hire_date", "exit_date"]).to_sql(
        "employees", con, index=False
    )
    payroll[["employee_id", "period", "fte", "gross_salary"]].to_sql("payroll", con, index=False)
    sources.units.to_sql("units", con, index=False)
    pd.DataFrame(
        {
            "period_start": [sources.period_start.strftime("%Y-%m-%d")],
            "reference_date": [sources.reference_date.strftime("%Y-%m-%d")],
        }
    ).to_sql("params", con, index=False)
    con.executescript(read_query("views"))
    return con


def query(con: sqlite3.Connection, name: str) -> pd.DataFrame:
    return pd.read_sql_query(read_query(name), con)
