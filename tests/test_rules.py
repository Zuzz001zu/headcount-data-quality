import pytest

from headcount.rules import RULES, excluded_employees, run_checks
from tests.conftest import employee, make_sources, pay


def rule_ids(sources):
    return run_checks(sources)["rule_id"].tolist()


def test_clean_data_has_no_issue(clean_sources):
    assert run_checks(clean_sources).empty


def test_rule_ids_are_unique():
    ids = [r.id for r in RULES]
    assert len(ids) == len(set(ids))


def test_duplicate_employee_id_is_reported_once():
    sources = make_sources(
        [employee("E10001"), employee("E10001", prenom="Marc"), employee("E10002")],
        [pay("E10001"), pay("E10002")],
    )
    assert rule_ids(sources).count("HR-01") == 1


def test_avs_shared_by_two_employees():
    first = employee("E10001")
    sources = make_sources(
        [first, employee("E10002", no_avs=first["no_avs"])],
        [pay("E10001"), pay("E10002")],
    )
    assert rule_ids(sources) == ["HR-02", "HR-02"]


def test_invalid_avs_number():
    sources = make_sources([employee("E10001", no_avs="756.9217.0769.84")], [pay("E10001")])
    assert rule_ids(sources) == ["HR-03"]


@pytest.mark.parametrize("column", ["nom", "prenom", "no_avs", "unite", "type_contrat"])
def test_missing_mandatory_field(column):
    sources = make_sources([employee("E10001", **{column: "  "})], [pay("E10001")])
    issues = run_checks(sources)
    assert issues["rule_id"].tolist() == ["HR-04"]
    assert issues["field"].iloc[0] == column


def test_unreadable_date():
    sources = make_sources([employee("E10001", date_naissance="31.02.1985")], [pay("E10001")])
    issues = run_checks(sources)
    assert issues["rule_id"].tolist() == ["HR-05"]
    assert issues["value"].iloc[0] == "31.02.1985"


def test_unknown_codes():
    sources = make_sources(
        [employee("E10001", sexe="X"), employee("E10002", type_contrat="INT")],
        [pay("E10001"), pay("E10002")],
    )
    assert rule_ids(sources) == ["HR-06", "HR-06"]


def test_unit_missing_from_reference_table():
    sources = make_sources([employee("E10001", unite="FIN-XXX")], [pay("E10001")])
    assert rule_ids(sources) == ["HR-07"]


def test_exit_before_hire():
    sources = make_sources(
        [employee("E10001", date_entree="01.03.2020", date_sortie="01.01.2020")], []
    )
    assert rule_ids(sources) == ["HR-08"]


@pytest.mark.parametrize("birth", ["01.01.2008", "01.01.1940"])
def test_implausible_age_at_hire_is_a_warning(birth):
    sources = make_sources(
        [employee("E10001", date_naissance=birth, date_entree="01.06.2020")], [pay("E10001")]
    )
    issues = run_checks(sources)
    assert issues["rule_id"].tolist() == ["HR-09"]
    assert excluded_employees(issues) == set()


def test_paid_but_unknown_in_hr(clean_sources):
    clean_sources.payroll.loc[len(clean_sources.payroll)] = clean_sources.payroll.iloc[0]
    clean_sources.payroll.loc[len(clean_sources.payroll) - 1, "employee_id"] = "E99999"
    assert rule_ids(clean_sources) == ["PAY-01"]


@pytest.mark.parametrize("fte", ["0", "120", "", "abc"])
def test_invalid_activity_rate(fte):
    sources = make_sources([employee("E10001")], [pay("E10001", fte=fte)])
    assert rule_ids(sources) == ["PAY-02"]


def test_two_contracts_are_fine_until_they_exceed_100_percent():
    ok = make_sources([employee("E10001")], [pay("E10001", "60"), pay("E10001", "40")])
    assert rule_ids(ok) == []

    too_much = make_sources([employee("E10001")], [pay("E10001", "80"), pay("E10001", "40")])
    assert rule_ids(too_much) == ["PAY-03"]


def test_paid_after_exit():
    sources = make_sources([employee("E10001", date_sortie="31.07.2026")], [pay("E10001")])
    assert rule_ids(sources) == ["PAY-04"]


def test_leaving_during_the_period_can_still_be_paid():
    sources = make_sources([employee("E10001", date_sortie="15.09.2026")], [pay("E10001")])
    assert rule_ids(sources) == []


def test_active_employee_without_salary():
    sources = make_sources([employee("E10001"), employee("E10002")], [pay("E10001")])
    issues = run_checks(sources)
    assert issues["rule_id"].tolist() == ["PAY-05"]
    assert issues["employee_id"].tolist() == ["E10002"]


def test_future_hire_is_not_expected_in_payroll():
    sources = make_sources([employee("E10001", date_entree="01.11.2026")], [])
    assert rule_ids(sources) == []


def test_row_from_another_period():
    sources = make_sources([employee("E10001")], [pay("E10001"), pay("E10001", period="2026-08")])
    assert rule_ids(sources) == ["PAY-06"]


def test_only_errors_exclude_employees():
    sources = make_sources(
        [employee("E10001", unite="FIN-XXX"), employee("E10002")],
        [pay("E10001")],
    )
    issues = run_checks(sources)
    assert set(issues["rule_id"]) == {"HR-07", "PAY-05"}
    assert excluded_employees(issues) == {"E10001"}
