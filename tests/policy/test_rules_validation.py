import copy

import pytest

from policy.rules import validate_rules


def test_example_rules_are_valid(example_rules):
    assert validate_rules(example_rules) == []


def test_not_an_object():
    assert validate_rules([1, 2]) == ["rules must be a JSON object"]
    assert validate_rules(None) == ["rules must be a JSON object"]


def test_missing_required_field_is_listed(example_rules):
    del example_rules["approval_tiers"]
    assert any("approval_tiers" in e for e in validate_rules(example_rules))


def test_unknown_top_level_field_rejected(example_rules):
    example_rules["surprise"] = 1
    assert validate_rules(example_rules)


@pytest.mark.parametrize("bad", ["2026-13-01", "2026-02-30", "20261104", "04-11-2026", "", "yesterday"])
def test_bad_effective_date(example_rules, bad):
    example_rules["effective_from"] = bad
    assert any("effective_from" in e for e in validate_rules(example_rules))


def test_last_tier_must_be_open_ended(example_rules):
    example_rules["approval_tiers"][-1]["max_total"] = 999999
    assert any("last tier" in e for e in validate_rules(example_rules))


def test_open_ended_tier_in_the_middle(example_rules):
    example_rules["approval_tiers"][1]["max_total"] = None
    assert any("only the last tier" in e for e in validate_rules(example_rules))


def test_tiers_must_increase(example_rules):
    example_rules["approval_tiers"][1]["max_total"] = 10000  # same as tier 1
    assert any("strictly increasing" in e for e in validate_rules(example_rules))
    example_rules["approval_tiers"][1]["max_total"] = 5000  # lower than tier 1
    assert any("strictly increasing" in e for e in validate_rules(example_rules))


def test_tier_cap_must_be_positive(example_rules):
    example_rules["approval_tiers"][0]["max_total"] = 0
    assert any("above zero" in e for e in validate_rules(example_rules))


def test_duplicate_tier_ids(example_rules):
    example_rules["approval_tiers"][1]["id"] = "T1"
    assert any("unique" in e for e in validate_rules(example_rules))


def test_same_role_twice_in_a_tier(example_rules):
    example_rules["approval_tiers"][1]["steps"] = ["LINE_MANAGER", "LINE_MANAGER"]
    assert any("same role twice" in e for e in validate_rules(example_rules))


def test_unknown_role_rejected(example_rules):
    example_rules["approval_tiers"][0]["steps"] = ["JANITOR"]
    assert validate_rules(example_rules)


def test_more_than_two_steps_rejected(example_rules):
    example_rules["approval_tiers"][0]["steps"] = ["LINE_MANAGER", "DEPARTMENT_HEAD", "CFO"]
    assert validate_rules(example_rules)


def test_category_missing_a_grade(example_rules):
    del example_rules["category_limits"]["Meals"]["G3"]
    assert any("Meals has no limit for grade G3" in e for e in validate_rules(example_rules))


def test_negative_limit(example_rules):
    example_rules["category_limits"]["Meals"]["G1"] = -1
    assert validate_rules(example_rules)  # the schema stops it first


def test_boolean_limit_is_not_a_number(example_rules):
    example_rules["category_limits"]["Meals"]["G1"] = True
    assert validate_rules(example_rules)


def test_text_limit_is_caught_by_the_extra_check(example_rules):
    example_rules["category_limits"]["Meals"]["G1"] = "lots"  # the schema allows text, the extra check does not
    assert any("0 or more" in e for e in validate_rules(example_rules))


def test_limit_for_unknown_grade(example_rules):
    example_rules["category_limits"]["Meals"]["G9"] = 100
    assert any("unknown grades" in e for e in validate_rules(example_rules))


def test_unknown_unit(example_rules):
    example_rules["category_limits"]["Meals"]["unit"] = "per_fortnight"
    assert validate_rules(example_rules)


def test_sod_flags_required(example_rules):
    del example_rules["segregation_of_duties"]["payer_cannot_approve"]
    assert validate_rules(example_rules)


def test_bad_currency_code(example_rules):
    example_rules["base_currency"] = "rupees"
    assert validate_rules(example_rules)


def test_negative_receipt_threshold(example_rules):
    example_rules["receipt_threshold"] = -5
    assert validate_rules(example_rules)


def test_empty_grades(example_rules):
    example_rules["grades"] = []
    assert validate_rules(example_rules)


def test_validation_does_not_change_input(example_rules):
    before = copy.deepcopy(example_rules)
    validate_rules(example_rules)
    assert example_rules == before
