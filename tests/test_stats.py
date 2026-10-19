from headcount.pipeline import analyse
from tests.conftest import employee, make_sources, pay


def test_headcount_counts_staff_present_on_the_last_day():
    sources = make_sources(
        [
            employee("E10001"),
            employee("E10002", sexe="M", unite="FOR-OBL"),
            employee("E10003", date_sortie="15.09.2026"),  # left during the month
            employee("E10004", date_entree="01.10.2026"),  # not started yet
        ],
        [pay("E10001", "100", "9000"), pay("E10002", "50", "4000"), pay("E10003", "100", "4500")],
    )
    result = analyse(sources)

    assert result.totals["headcount"] == 2
    assert result.totals["fte"] == 1.5
    assert result.totals["payroll_total"] == 13000


def test_employees_with_blocking_issues_are_left_out():
    sources = make_sources(
        [employee("E10001"), employee("E10002", no_avs="756.9217.0769.84")],
        [pay("E10001"), pay("E10002")],
    )
    result = analyse(sources)

    assert result.excluded == {"E10002"}
    assert result.totals["headcount"] == 1


def test_department_table():
    sources = make_sources(
        [
            employee("E10001"),
            employee("E10002", sexe="M"),
            employee("E10003", unite="FOR-OBL"),
        ],
        [pay("E10001", "100"), pay("E10002", "60"), pay("E10003", "80")],
    )
    table = analyse(sources).tables["headcount_by_department"].set_index("department")

    finances = table.loc["Finances"]
    assert finances["headcount"] == 2
    assert finances["fte"] == 1.6
    assert finances["women"] == 1
    assert finances["women_pct"] == 50.0
    assert table.loc["Formation", "headcount"] == 1


def test_two_contracts_count_as_one_person():
    sources = make_sources([employee("E10001")], [pay("E10001", "60"), pay("E10001", "40")])
    assert analyse(sources).totals == {
        "headcount": 1,
        "fte": 1.0,
        "average_activity_rate": 100.0,
        "payroll_total": 16000.0,
    }


def test_age_bands():
    sources = make_sources(
        [
            employee("E10001", date_naissance="01.01.2003", date_entree="01.01.2024"),
            employee("E10002", date_naissance="01.01.1970"),
        ],
        [pay("E10001"), pay("E10002")],
    )
    ages = analyse(sources).tables["headcount_by_age"].set_index("age_band")["headcount"]
    assert ages.to_dict() == {"< 25": 1, "55+": 1}
