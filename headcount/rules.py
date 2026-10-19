"""Data quality rules.

Each rule receives the loaded sources and returns the offending rows as a frame
with the columns employee_id, field and value. Rules are registered with the
@rule decorator; run_checks() runs all of them and adds the rule metadata.

Severity:
- "error": the employee is excluded from the statistics until the data is fixed
- "warning": the record is kept but should be reviewed
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from headcount import avs
from headcount.load import Sources

ERROR = "error"
WARNING = "warning"

GENDERS = {"F", "M"}
CONTRACT_TYPES = {"CDI", "CDD", "AUX"}
MANDATORY_FIELDS = {
    "employee_id": "matricule",
    "last_name": "nom",
    "first_name": "prenom",
    "avs": "no_avs",
    "birth_date_raw": "date_naissance",
    "gender": "sexe",
    "unit_code": "unite",
    "hire_date_raw": "date_entree",
    "contract_type": "type_contrat",
}
MIN_AGE_AT_HIRE = 15
MAX_AGE_AT_HIRE = 70

ISSUE_COLUMNS = ["rule_id", "severity", "source", "employee_id", "field", "value", "description"]
SOURCE_NAMES = {"HR": "SIRH", "PAY": "Salaires"}

RuleFunc = Callable[[Sources], pd.DataFrame]


@dataclass(frozen=True)
class Rule:
    id: str
    severity: str
    description: str
    check: RuleFunc

    @property
    def source(self) -> str:
        return SOURCE_NAMES[self.id.split("-")[0]]


RULES: list[Rule] = []


def rule(rule_id: str, severity: str, description: str) -> Callable[[RuleFunc], RuleFunc]:
    def register(func: RuleFunc) -> RuleFunc:
        RULES.append(Rule(rule_id, severity, description, func))
        return func

    return register


def found(rows: pd.DataFrame, field: str, value_column: str | None = None) -> pd.DataFrame:
    values = rows[value_column or field]
    return pd.DataFrame(
        {
            "employee_id": rows["employee_id"].astype("string").to_numpy(),
            "field": field,
            "value": values.astype("string").to_numpy(),
        }
    )


def active_employees(sources: Sources) -> pd.DataFrame:
    """Employees under contract at some point during the period."""
    e = sources.employees
    started = e["hire_date"] <= sources.reference_date
    not_left = e["exit_date"].isna() | (e["exit_date"] >= sources.period_start)
    return e[started & not_left]


def payroll_in_period(sources: Sources) -> pd.DataFrame:
    p = sources.payroll
    return p[p["period"] == str(sources.period)]


# --- HR system --------------------------------------------------------------


@rule("HR-01", ERROR, "Matricule en double")
def duplicate_employee_id(sources: Sources) -> pd.DataFrame:
    e = sources.employees.dropna(subset=["employee_id"])
    dupes = e[e["employee_id"].duplicated(keep=False)].drop_duplicates("employee_id")
    return found(dupes, "matricule", "employee_id")


@rule("HR-02", ERROR, "Même numéro AVS pour plusieurs matricules")
def shared_avs_number(sources: Sources) -> pd.DataFrame:
    e = sources.employees.dropna(subset=["avs", "employee_id"])
    ids_per_avs = e.groupby("avs")["employee_id"].nunique()
    shared = ids_per_avs[ids_per_avs > 1].index
    return found(e[e["avs"].isin(shared)], "no_avs", "avs")


@rule("HR-03", ERROR, "Numéro AVS invalide (format ou chiffre de contrôle)")
def invalid_avs_number(sources: Sources) -> pd.DataFrame:
    e = sources.employees.dropna(subset=["avs"])
    return found(e[~e["avs"].map(avs.is_valid).astype(bool)], "no_avs", "avs")


@rule("HR-04", ERROR, "Champ obligatoire manquant")
def missing_mandatory_field(sources: Sources) -> pd.DataFrame:
    e = sources.employees
    parts = [
        found(e[e[column].isna()], label, column) for column, label in MANDATORY_FIELDS.items()
    ]
    return pd.concat(parts, ignore_index=True)


@rule("HR-05", ERROR, "Date illisible")
def unreadable_date(sources: Sources) -> pd.DataFrame:
    e = sources.employees
    labels = {
        "birth_date": "date_naissance",
        "hire_date": "date_entree",
        "exit_date": "date_sortie",
    }
    parts = []
    for column, label in labels.items():
        raw = f"{column}_raw"
        parts.append(found(e[e[raw].notna() & e[column].isna()], label, raw))
    return pd.concat(parts, ignore_index=True)


@rule("HR-06", ERROR, "Code hors nomenclature (sexe ou type de contrat)")
def unknown_code(sources: Sources) -> pd.DataFrame:
    e = sources.employees
    bad_gender = e[e["gender"].notna() & ~e["gender"].isin(GENDERS)]
    bad_contract = e[e["contract_type"].notna() & ~e["contract_type"].isin(CONTRACT_TYPES)]
    return pd.concat(
        [found(bad_gender, "sexe", "gender"), found(bad_contract, "type_contrat", "contract_type")],
        ignore_index=True,
    )


@rule("HR-07", ERROR, "Unité absente du référentiel")
def unknown_unit(sources: Sources) -> pd.DataFrame:
    e = sources.employees
    known = set(sources.units["unit_code"].dropna())
    return found(e[e["unit_code"].notna() & ~e["unit_code"].isin(known)], "unite", "unit_code")


@rule("HR-08", ERROR, "Date de sortie antérieure à la date d'entrée")
def exit_before_hire(sources: Sources) -> pd.DataFrame:
    e = sources.employees
    return found(e[e["exit_date"] < e["hire_date"]], "date_sortie", "exit_date_raw")


@rule("HR-09", WARNING, f"Âge à l'entrée hors de {MIN_AGE_AT_HIRE}-{MAX_AGE_AT_HIRE} ans")
def implausible_age_at_hire(sources: Sources) -> pd.DataFrame:
    e = sources.employees
    age = (e["hire_date"] - e["birth_date"]).dt.days / 365.25
    suspicious = e[(age < MIN_AGE_AT_HIRE) | (age > MAX_AGE_AT_HIRE)]
    return found(suspicious, "date_naissance", "birth_date_raw")


# --- Payroll ----------------------------------------------------------------


@rule("PAY-01", ERROR, "Salaire versé à un matricule inconnu du SIRH")
def paid_but_unknown(sources: Sources) -> pd.DataFrame:
    p = payroll_in_period(sources)
    known = set(sources.employees["employee_id"].dropna())
    return found(p[~p["employee_id"].isin(known)], "matricule", "employee_id")


@rule("PAY-02", ERROR, "Taux d'activité illisible ou hors de ]0 ; 100]")
def invalid_fte(sources: Sources) -> pd.DataFrame:
    p = payroll_in_period(sources)
    bad = p["fte"].isna() | (p["fte"] <= 0) | (p["fte"] > 100)
    return found(p[bad], "taux_activite", "fte_raw")


@rule("PAY-03", ERROR, "Taux d'activité cumulé supérieur à 100 %")
def fte_over_100(sources: Sources) -> pd.DataFrame:
    p = payroll_in_period(sources)
    p = p[(p["fte"] > 0) & (p["fte"] <= 100)]
    total = p.groupby("employee_id", as_index=False)["fte"].sum()
    return found(total[total["fte"] > 100], "taux_activite", "fte")


@rule("PAY-04", ERROR, "Salaire versé après la date de sortie")
def paid_after_exit(sources: Sources) -> pd.DataFrame:
    p = payroll_in_period(sources)
    e = sources.employees.dropna(subset=["employee_id"]).drop_duplicates("employee_id")
    merged = p.merge(e[["employee_id", "exit_date", "exit_date_raw"]], on="employee_id")
    left = merged[merged["exit_date"] < sources.period_start].drop_duplicates("employee_id")
    return found(left, "date_sortie", "exit_date_raw")


@rule("PAY-05", WARNING, "Collaborateur actif sans salaire sur la période")
def active_but_not_paid(sources: Sources) -> pd.DataFrame:
    paid = set(payroll_in_period(sources)["employee_id"].dropna())
    active = active_employees(sources).dropna(subset=["employee_id"])
    return found(active[~active["employee_id"].isin(paid)], "matricule", "employee_id")


@rule("PAY-06", WARNING, "Ligne de salaire hors période")
def wrong_period(sources: Sources) -> pd.DataFrame:
    p = sources.payroll
    return found(p[p["period"] != str(sources.period)], "periode", "period")


def run_checks(sources: Sources, rules: list[Rule] | None = None) -> pd.DataFrame:
    frames = []
    for r in rules or RULES:
        result = r.check(sources)
        if result.empty:
            continue
        frames.append(
            result.assign(
                rule_id=r.id, severity=r.severity, source=r.source, description=r.description
            )
        )
    if not frames:
        return pd.DataFrame(columns=ISSUE_COLUMNS)
    return pd.concat(frames, ignore_index=True)[ISSUE_COLUMNS]


def excluded_employees(issues: pd.DataFrame) -> set[str]:
    blocking = issues[issues["severity"] == ERROR]["employee_id"].dropna()
    return set(blocking)
