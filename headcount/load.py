"""Read the three source files and bring them to a common shape.

Source exports use French column names and are not consistent: dates come in
several formats, codes in mixed case, amounts with Swiss thousand separators.
Raw date strings are kept next to the parsed values so that the quality rules
can report what was actually in the file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from headcount import avs

EMPLOYEE_COLUMNS = {
    "matricule": "employee_id",
    "nom": "last_name",
    "prenom": "first_name",
    "no_avs": "avs",
    "date_naissance": "birth_date",
    "sexe": "gender",
    "unite": "unit_code",
    "date_entree": "hire_date",
    "date_sortie": "exit_date",
    "type_contrat": "contract_type",
}
PAYROLL_COLUMNS = {
    "matricule": "employee_id",
    "periode": "period",
    "taux_activite": "fte",
    "salaire_brut": "gross_salary",
}
UNIT_COLUMNS = {
    "code_unite": "unit_code",
    "libelle": "unit_name",
    "departement": "department",
}

DATE_COLUMNS = ("birth_date", "hire_date", "exit_date")
DATE_FORMATS = ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y")

EMPLOYEES_FILE = "sirh_collaborateurs.csv"
UNITS_FILE = "referentiel_unites.csv"


def payroll_file(period: pd.Period) -> str:
    return f"salaires_{period}.xlsx"


@dataclass
class Sources:
    employees: pd.DataFrame
    payroll: pd.DataFrame
    units: pd.DataFrame
    period: pd.Period

    @property
    def period_start(self) -> pd.Timestamp:
        return self.period.start_time.normalize()

    @property
    def reference_date(self) -> pd.Timestamp:
        """Headcount is measured on the last day of the period."""
        return self.period.end_time.normalize()


def clean_text(series: pd.Series) -> pd.Series:
    cleaned = series.astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
    return cleaned.mask(cleaned.eq("").fillna(False))


def parse_dates(series: pd.Series) -> pd.Series:
    values = clean_text(series)
    parsed = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    for fmt in DATE_FORMATS:
        attempt = pd.to_datetime(values, format=fmt, errors="coerce")
        parsed = parsed.fillna(attempt.astype("datetime64[ns]"))
    return parsed


def parse_number(series: pd.Series) -> pd.Series:
    """Parse '6'450.50', '80 %' or '50,5'. Anything else becomes NaN."""
    values = (
        clean_text(series)
        .str.replace("%", "", regex=False)
        .str.replace("'", "", regex=False)
        .str.replace("\N{RIGHT SINGLE QUOTATION MARK}", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    return pd.to_numeric(values, errors="coerce").astype("float64")


def normalize_employees(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(columns=EMPLOYEE_COLUMNS)[list(EMPLOYEE_COLUMNS.values())].copy()
    for column in df.columns:
        df[column] = clean_text(df[column])

    df["employee_id"] = df["employee_id"].str.upper()
    df["unit_code"] = df["unit_code"].str.upper()
    df["gender"] = df["gender"].str.upper()
    df["contract_type"] = df["contract_type"].str.upper()
    df["last_name"] = df["last_name"].str.title()
    df["first_name"] = df["first_name"].str.title()
    df["avs"] = df["avs"].map(lambda v: avs.normalize(v) or v, na_action="ignore")

    for column in DATE_COLUMNS:
        df[f"{column}_raw"] = df[column]
        df[column] = parse_dates(df[column])
    return df


def normalize_payroll(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(columns=PAYROLL_COLUMNS)[list(PAYROLL_COLUMNS.values())].copy()
    df["employee_id"] = clean_text(df["employee_id"]).str.upper()
    df["period"] = clean_text(df["period"])
    df["fte_raw"] = clean_text(df["fte"])
    df["fte"] = parse_number(df["fte"])
    df["gross_salary"] = parse_number(df["gross_salary"])
    return df


def normalize_units(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(columns=UNIT_COLUMNS)[list(UNIT_COLUMNS.values())].copy()
    for column in df.columns:
        df[column] = clean_text(df[column])
    df["unit_code"] = df["unit_code"].str.upper()
    return df


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep=";", dtype=str, encoding="utf-8-sig", keep_default_na=False)


def load_sources(raw_dir: Path, period: pd.Period) -> Sources:
    raw_dir = Path(raw_dir)
    payroll_path = raw_dir / payroll_file(period)
    if not payroll_path.exists():
        raise FileNotFoundError(f"payroll export for {period} not found: {payroll_path}")

    return Sources(
        employees=normalize_employees(_read_csv(raw_dir / EMPLOYEES_FILE)),
        payroll=normalize_payroll(pd.read_excel(payroll_path, dtype=str)),
        units=normalize_units(_read_csv(raw_dir / UNITS_FILE)),
        period=period,
    )
