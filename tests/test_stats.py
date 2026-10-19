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


def test_entries_and_exits_of_the_period():
    sources = make_sources(
        [
            employee("E10001"),
            employee("E10002", date_entree="14.09.2026"),
            employee("E10003", date_sortie="15.09.2026"),
            employee("E10004", date_sortie="30.09.2026"),  # last day: still in headcount
            employee("E10005", date_sortie="31.08.2026"),  # previous month
            employee("E10006", unite="FOR-OBL", date_entree="01.09.2026"),
        ],
        [pay(i) for i in ["E10001", "E10002", "E10003", "E10004", "E10006"]],
    )
    result = analyse(sources)
    moves = result.tables["movements_by_department"].set_index("department")

    assert moves.loc["Finances"].to_dict() == {
        "entries": 1,
        "exits": 2,
        "net_change": -1,
        "exit_rate_pct": round(100 * 2 / 3, 1),
    }
    assert moves.loc["Formation", "entries"] == 1
    assert result.totals["headcount"] == 4

    people = result.tables["movements_list"]
    assert people["movement"].tolist() == ["Entrée", "Entrée", "Sortie", "Sortie"]
    assert people["employee_id"].tolist() == ["E10006", "E10002", "E10003", "E10004"]


def test_department_without_movement_is_listed_with_zeros(clean_sources):
    moves = analyse(clean_sources).tables["movements_by_department"]
    assert moves["entries"].sum() == 0
    assert set(moves["department"]) == {"Finances", "Formation"}
