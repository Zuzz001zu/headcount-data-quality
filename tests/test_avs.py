import pytest

from headcount import avs


def test_official_example_is_valid():
    # example number published by the Swiss Central Compensation Office
    assert avs.is_valid("756.9217.0769.85")


@pytest.mark.parametrize(
    "value",
    [
        "756.9217.0769.84",  # wrong check digit
        "755.9217.0769.85",  # wrong country prefix
        "756.9217.0769",  # too short
        "756.9217.0769.8A",
        "",
    ],
)
def test_invalid_numbers(value):
    assert not avs.is_valid(value)


def test_normalize_accepts_missing_dots_and_spaces():
    assert avs.normalize("7569217076985") == "756.9217.0769.85"
    assert avs.normalize(" 756 9217 0769 85 ") == "756.9217.0769.85"


def test_build_produces_valid_numbers():
    for body in ["000000000", "123456789", "999999999"]:
        assert avs.is_valid(avs.build(body))
