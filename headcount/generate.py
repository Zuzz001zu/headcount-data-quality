"""Generate realistic but fictional source files for a cantonal administration.

Real HR data cannot be published, so the sample data is generated. The generator
writes the same three exports the pipeline expects and deliberately injects a
known number of anomalies of each kind. The test suite uses those numbers to
check that every rule finds exactly what was injected.

All names, AVS numbers and salaries are made up.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from headcount import avs
from headcount.load import EMPLOYEES_FILE, UNITS_FILE, payroll_file

UNITS = [
    ("FIN-CPT", "Comptabilité générale", "Finances"),
    ("FIN-IMP", "Administration des impôts", "Finances"),
    ("FIN-SIN", "Systèmes d'information", "Finances"),
    ("SAN-HOP", "Coordination hospitalière", "Santé et action sociale"),
    ("SAN-AID", "Aide sociale", "Santé et action sociale"),
    ("SAN-PRE", "Prévention et promotion de la santé", "Santé et action sociale"),
    ("FOR-OBL", "Enseignement obligatoire", "Formation"),
    ("FOR-PRO", "Formation professionnelle", "Formation"),
    ("INF-ROU", "Routes et ouvrages d'art", "Infrastructures"),
    ("INF-BAT", "Bâtiments", "Infrastructures"),
    ("SEC-POL", "Police administrative", "Sécurité"),
    ("SEC-PCI", "Protection civile", "Sécurité"),
    ("TER-ENV", "Environnement", "Territoire et environnement"),
    ("TER-AMT", "Aménagement du territoire", "Territoire et environnement"),
]
UNIT_WEIGHTS = [5, 8, 3, 4, 6, 2, 14, 7, 5, 3, 6, 2, 3, 2]

FIRST_NAMES_F = (
    "Anne Camille Chloé Claire Elodie Emma Isabelle Julie Laura Léa Lucie Manon Marie "
    "Mathilde Nathalie Sandra Sarah Sophie Valérie Céline"
).split()
FIRST_NAMES_M = (
    "Alain Antoine Christophe David Fabien François Julien Laurent Luca Marc Mathieu "
    "Nicolas Olivier Patrick Pierre Romain Sébastien Stéphane Thomas Yves"
).split()
LAST_NAMES = (
    "Aebischer Berger Blanc Bonvin Chevalley Cuendet Dubois Favre Gay Gilliéron Jaquier "
    "Martin Meylan Monnier Morel Muller Pasche Perret Pittet Rey Rochat Roulin Savary "
    "Schmid Tissot Vuilleumier Zbinden Ferreira Rossi Nguyen"
).split()

DATE_FORMATS = ["%d.%m.%Y"] * 7 + ["%Y-%m-%d"] * 2 + ["%d/%m/%Y"]
FTE_CHOICES = [100] * 6 + [90, 80, 80, 70, 60, 50, 40]


@dataclass
class Generated:
    employees: pd.DataFrame
    payroll: pd.DataFrame
    units: pd.DataFrame
    injected: dict[str, int] = field(default_factory=dict)


class _Generator:
    def __init__(self, period: pd.Period, size: int, seed: int) -> None:
        self.rng = random.Random(seed)
        self.period = period
        self.start = period.start_time.date()
        self.end = period.end_time.date()
        self.size = size
        self.used_avs: set[str] = set()
        self.injected: dict[str, int] = {}

    # -- building blocks --------------------------------------------------

    def random_date(self, low: date, high: date) -> date:
        return low + timedelta(days=self.rng.randint(0, (high - low).days))

    def new_avs(self) -> str:
        while True:
            number = avs.build(f"{self.rng.randint(0, 999_999_999):09d}")
            if number not in self.used_avs:
                self.used_avs.add(number)
                return number

    def person(self, employee_id: str, status: str) -> dict:
        rng = self.rng
        gender = rng.choice("FM")
        first = rng.choice(FIRST_NAMES_F if gender == "F" else FIRST_NAMES_M)

        if status == "joined":
            hire = self.random_date(self.start, self.end)
        elif status == "future":
            hire = self.end + timedelta(days=rng.randint(1, 60))
        else:
            # more recent hires than old ones, as in most administrations
            hire = self.start - timedelta(days=int(rng.triangular(120, 30 * 365, 120)))

        exit_ = None
        if status == "left":
            exit_ = self.random_date(hire + timedelta(days=90), self.start - timedelta(days=1))
        elif status == "leaving":
            exit_ = self.random_date(self.start, self.end - timedelta(days=1))

        age_at_hire = rng.randint(21, 48)
        birth = hire - timedelta(days=int(age_at_hire * 365.25) + rng.randint(0, 364))
        while (self.end - birth).days / 365.25 > 64.5:
            birth += timedelta(days=365)

        contract = rng.choices(["CDI", "CDD", "AUX"], weights=[75, 18, 7])[0]
        unit = rng.choices([u[0] for u in UNITS], weights=UNIT_WEIGHTS)[0]
        return {
            "matricule": employee_id,
            "nom": rng.choice(LAST_NAMES),
            "prenom": first,
            "no_avs": self.new_avs(),
            "date_naissance": birth,
            "sexe": gender,
            "unite": unit,
            "date_entree": hire,
            "date_sortie": exit_,
            "type_contrat": contract,
            "_status": status,
        }

    def salary(self, fte: float) -> float:
        monthly_full_time = self.rng.randint(5_200, 11_800)
        return round(monthly_full_time * fte / 100 * 20) / 20

    def mark(self, rule_id: str, count: int = 1) -> None:
        self.injected[rule_id] = self.injected.get(rule_id, 0) + count

    # -- main ---------------------------------------------------------------

    def run(self) -> Generated:
        rng = self.rng
        statuses = rng.choices(
            ["active", "left", "leaving", "joined", "future"],
            weights=[85, 7, 3, 3, 2],
            k=self.size,
        )
        ids = [f"E{n}" for n in rng.sample(range(10_000, 99_000), self.size)]
        people = [self.person(i, s) for i, s in zip(ids, statuses, strict=True)]

        paid_statuses = {"active", "leaving", "joined"}
        pool = [p for p in people if p["_status"] == "active"]
        rng.shuffle(pool)
        left_pool = [p for p in people if p["_status"] == "left"]
        rng.shuffle(left_pool)

        # Payroll for everybody under contract during the period, before any error.
        payroll = []
        for p in people:
            if p["_status"] not in paid_statuses:
                continue
            fte = rng.choice(FTE_CHOICES)
            if fte == 100 and rng.random() < 0.04:
                # two part-time contracts for the same person are legitimate
                payroll.append(self.pay_row(p["matricule"], 60))
                payroll.append(self.pay_row(p["matricule"], 40))
            else:
                payroll.append(self.pay_row(p["matricule"], fte))

        self.inject_hr_errors(people, pool, left_pool)
        payroll = self.inject_payroll_errors(payroll, pool, left_pool)

        employees = pd.DataFrame([self.format_person(p) for p in people])
        employees = employees.sample(frac=1, random_state=rng.randint(0, 10_000))
        units = pd.DataFrame(UNITS, columns=["code_unite", "libelle", "departement"])
        return Generated(
            employees=employees.reset_index(drop=True),
            payroll=pd.DataFrame(payroll),
            units=units,
            injected=dict(sorted(self.injected.items())),
        )

    def pay_row(self, employee_id: str, fte: float, period: str | None = None) -> dict:
        return {
            "matricule": employee_id,
            "periode": period or str(self.period),
            "taux_activite": fte,
            "salaire_brut": self.salary(fte) if isinstance(fte, int | float) else 6_000.0,
        }

    def inject_hr_errors(self, people: list[dict], pool: list[dict], left_pool: list[dict]) -> None:
        rng = self.rng

        for original in [pool.pop() for _ in range(3)]:
            copy = self.person(original["matricule"], "active")
            people.append(copy)
            self.mark("HR-01")

        for _ in range(2):
            a, b = pool.pop(), pool.pop()
            b["no_avs"] = a["no_avs"]
            self.mark("HR-02", 2)

        for p in [pool.pop() for _ in range(5)]:
            digits = p["no_avs"].replace(".", "")
            wrong = digits[:-1] + str((int(digits[-1]) + rng.randint(1, 9)) % 10)
            p["no_avs"] = avs.normalize(wrong)
            self.mark("HR-03")

        for column in ["unite", "no_avs", "prenom", "type_contrat"]:
            pool.pop()[column] = ""
            self.mark("HR-04")

        pool.pop()["date_naissance"] = "31.02.1985"
        pool.pop()["date_entree"] = "2019-13-01"
        pool.pop()["date_naissance"] = "n/a"
        self.mark("HR-05", 3)

        pool.pop()["sexe"] = "X"
        pool.pop()["type_contrat"] = "INT"
        self.mark("HR-06", 2)

        for code in ["FIN-CTP", "SAN-XXX", "FOR-SEC"]:
            pool.pop()["unite"] = code
            self.mark("HR-07")

        # Former employees, so the wrong exit date does not affect payroll checks.
        for p in [left_pool.pop() for _ in range(2)]:
            p["date_sortie"] = p["date_entree"] - timedelta(days=rng.randint(30, 400))
            self.mark("HR-08")

        young, old = pool.pop(), pool.pop()
        young["date_naissance"] = young["date_entree"] - timedelta(days=14 * 365)
        old["date_naissance"] = old["date_entree"] - timedelta(days=76 * 365)
        self.mark("HR-09", 2)

        # Cosmetic inconsistencies that the loader is expected to absorb.
        for p in people:
            if rng.random() < 0.05:
                p["sexe"] = p["sexe"].lower()
            if rng.random() < 0.05:
                p["nom"] = f"  {p['nom'].upper()} "
            if rng.random() < 0.10 and p["no_avs"]:
                p["no_avs"] = p["no_avs"].replace(".", "")

    def inject_payroll_errors(
        self, payroll: list[dict], pool: list[dict], left_pool: list[dict]
    ) -> list[dict]:
        rng = self.rng
        by_id = {row["matricule"]: row for row in payroll}

        for _ in range(4):
            payroll.append(self.pay_row(f"E{rng.randint(99_100, 99_999)}", 80))
            self.mark("PAY-01")

        for value in [0, 120, "", "abc"]:
            row = by_id[pool.pop()["matricule"]]
            row["taux_activite"] = value
            self.mark("PAY-02")

        for p in [pool.pop() for _ in range(2)]:
            by_id[p["matricule"]]["taux_activite"] = 80
            payroll.append(self.pay_row(p["matricule"], 40))
            self.mark("PAY-03")

        for p in [left_pool.pop() for _ in range(3)]:
            payroll.append(self.pay_row(p["matricule"], 100))
            self.mark("PAY-04")

        unpaid = {pool.pop()["matricule"] for _ in range(5)}
        payroll = [row for row in payroll if row["matricule"] not in unpaid]
        self.mark("PAY-05", 5)

        previous = str(self.period - 1)
        for p in [pool.pop() for _ in range(2)]:
            payroll.append(self.pay_row(p["matricule"], 100, period=previous))
            self.mark("PAY-06")

        for row in payroll:
            fte = row["taux_activite"]
            if isinstance(fte, int) and fte and rng.random() < 0.1:
                row["taux_activite"] = f"{fte} %"
            if rng.random() < 0.3:
                row["salaire_brut"] = f"{row['salaire_brut']:,.2f}".replace(",", "'")
        rng.shuffle(payroll)
        return payroll

    def format_person(self, p: dict) -> dict:
        row = {k: v for k, v in p.items() if not k.startswith("_")}
        for column in ("date_naissance", "date_entree", "date_sortie"):
            value = row[column]
            if isinstance(value, date):
                row[column] = value.strftime(self.rng.choice(DATE_FORMATS))
            elif value is None:
                row[column] = ""
        return row


MIN_SIZE = 150  # enough employees to inject every anomaly on distinct people


def generate(period: pd.Period, size: int = 600, seed: int = 42) -> Generated:
    if size < MIN_SIZE:
        raise ValueError(f"size must be at least {MIN_SIZE}, got {size}")
    return _Generator(period, size, seed).run()


def write_sources(data: Generated, out_dir: Path, period: pd.Period) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [out_dir / EMPLOYEES_FILE, out_dir / UNITS_FILE, out_dir / payroll_file(period)]
    data.employees.to_csv(paths[0], sep=";", index=False, encoding="utf-8-sig")
    data.units.to_csv(paths[1], sep=";", index=False, encoding="utf-8-sig")
    data.payroll.to_excel(paths[2], index=False, sheet_name="Salaires")
    return paths
