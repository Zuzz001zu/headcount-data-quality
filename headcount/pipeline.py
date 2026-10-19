"""Load -> check -> consolidate -> aggregate, without any output formatting."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from headcount.db import build_database, query
from headcount.load import Sources, load_sources
from headcount.rules import ERROR, WARNING, excluded_employees, run_checks

TABLES = [
    "headcount_by_department",
    "headcount_by_unit",
    "headcount_by_contract",
    "headcount_by_age",
    "movements_by_department",
    "movements_list",
]


@dataclass
class Result:
    sources: Sources
    issues: pd.DataFrame
    excluded: set[str]
    totals: dict[str, float]
    tables: dict[str, pd.DataFrame]

    @property
    def errors(self) -> int:
        return int((self.issues["severity"] == ERROR).sum())

    @property
    def excluded_employees(self) -> int:
        """Employees known in the HR system and left out of the statistics."""
        known = set(self.sources.employees["employee_id"].dropna())
        return len(self.excluded & known)

    @property
    def warnings(self) -> int:
        return int((self.issues["severity"] == WARNING).sum())


def run(raw_dir: Path, period: pd.Period) -> Result:
    sources = load_sources(raw_dir, period)
    return analyse(sources)


def analyse(sources: Sources) -> Result:
    issues = run_checks(sources)
    excluded = excluded_employees(issues)
    con = build_database(sources, excluded)
    try:
        totals = query(con, "totals").iloc[0].fillna(0).to_dict()
        tables = {name: query(con, name) for name in TABLES}
    finally:
        con.close()
    return Result(sources, issues, excluded, totals, tables)
