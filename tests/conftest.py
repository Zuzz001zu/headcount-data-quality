import pandas as pd
import pytest

from headcount import avs
from headcount.load import Sources, normalize_employees, normalize_payroll, normalize_units

PERIOD = pd.Period("2026-09", freq="M")
PAYROLL_HEADER = ["matricule", "periode", "taux_activite", "salaire_brut"]

UNITS = [
    {"code_unite": "FIN-CPT", "libelle": "Comptabilité", "departement": "Finances"},
    {"code_unite": "FOR-OBL", "libelle": "Enseignement", "departement": "Formation"},
]


def employee(employee_id: str, **overrides) -> dict:
    """A valid HR record; override any French column to break it."""
    row = {
        "matricule": employee_id,
        "nom": "Favre",
        "prenom": "Anne",
        "no_avs": avs.build(f"{int(employee_id[1:]):09d}"),
        "date_naissance": "12.03.1985",
        "sexe": "F",
        "unite": "FIN-CPT",
        "date_entree": "01.02.2015",
        "date_sortie": "",
        "type_contrat": "CDI",
    }
    row.update(overrides)
    return row


def pay(employee_id: str, fte="100", salary="8000", period: str = str(PERIOD)) -> dict:
    return {
        "matricule": employee_id,
        "periode": period,
        "taux_activite": fte,
        "salaire_brut": salary,
    }


def make_sources(employees: list[dict], payroll: list[dict], period=PERIOD) -> Sources:
    return Sources(
        employees=normalize_employees(pd.DataFrame(employees, dtype=str)),
        payroll=normalize_payroll(pd.DataFrame(payroll, columns=PAYROLL_HEADER, dtype=str)),
        units=normalize_units(pd.DataFrame(UNITS)),
        period=period,
    )


@pytest.fixture
def clean_sources() -> Sources:
    return make_sources(
        [employee("E10001"), employee("E10002", sexe="M", unite="FOR-OBL")],
        [pay("E10001"), pay("E10002", fte="80")],
    )
