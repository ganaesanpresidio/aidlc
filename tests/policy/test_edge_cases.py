import copy
from datetime import UTC, datetime

import pytest

from policy.errors import PolicyError
from policy.service import PolicyService
from tests.policy.conftest import evaluate_body, line, route_body


def publish(service, rules, key="key-00000001"):
    return service.publish(copy.deepcopy(rules), actor="f", groups=["finance-admin"], idempotency_key=key)


def codes(r):
    return [v["code"] for v in r["violations"]]


# ---- numbers that are not numbers -------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity", "sNaN", "", " ", "1,000", "0x10", [], {}])
def test_text_that_looks_like_a_number_is_not_accepted(published, bad):
    with pytest.raises(PolicyError) as e:
        published.evaluate(evaluate_body([line(amount=bad)]))
    assert e.value.status == 400


@pytest.mark.parametrize("zero", [0, -0, 0.0, "0", "-0", "0.00"])
def test_every_kind_of_zero_amount_is_refused(published, zero):
    with pytest.raises(PolicyError):
        published.evaluate(evaluate_body([line(amount=zero)]))


def test_numbers_as_text_work(published):
    assert published.evaluate(evaluate_body([line(amount="500.50")]))["ok"]


def test_very_large_amounts_are_just_over_limit(published):
    r = published.evaluate(evaluate_body([line(amount="1e12", category="Other")]))
    assert "LIMIT_EXCEEDED" in codes(r)


@pytest.mark.parametrize("field,value", [("amount", "1e999999999"), ("amount", 10 ** 15 + 1), ("amount", "1e400"),
                                         ("quantity", "1e999999"), ("quantity", 10 ** 16), ("amountInr", "1e999999")])
def test_absurd_numbers_are_a_clean_400_not_a_crash(published, field, value):
    with pytest.raises(PolicyError) as e:
        published.evaluate(evaluate_body([line(category="Mileage", **{field: value})]))
    assert e.value.status == 400 and "too large" in e.value.message


def test_the_biggest_allowed_number_still_works(published):
    r = published.evaluate(evaluate_body([line(category="Mileage", amount=10 ** 15, quantity=10 ** 15)]))
    assert r["ok"] is True  # 10^15 km at 12 a km is a huge cap, and the amount is within it


def test_absurd_numbers_through_the_api_are_400_not_500(published):
    from policy.api import Auth, Request, handle
    body = evaluate_body([line(category="Mileage", quantity="1e999999")])
    r = handle(published, Request("POST", "/v1/policy/evaluate", body=body, auth=Auth("iam", principal="submit")))
    assert r.status == 400


def test_tiny_amounts_are_fine(published):
    assert published.evaluate(evaluate_body([line(amount="0.01")]))["ok"]


# ---- dates ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["2026-02-29", "2025-02-29", "2026-00-10", "2026-04-31", "0000-01-01", "2026-1-5", "２０２６-１１-０４"])
def test_impossible_dates_are_refused(published, bad):
    with pytest.raises(PolicyError) as e:
        published.evaluate(evaluate_body([line(expenseDate=bad)]))
    assert e.value.code == "INVALID_DATE"


def test_leap_day_is_a_real_date(service, example_rules, clock):
    clock.set(datetime(2028, 3, 1, 9, 0, tzinfo=UTC))
    example_rules["effective_from"] = "2028-03-01"
    publish(service, example_rules)
    r = service.evaluate(evaluate_body([line(expenseDate="2028-02-29")], submission="2028-03-01"))
    assert r["ok"]


def test_window_across_the_year_end(service, example_rules, clock):
    clock.set(datetime(2027, 1, 10, 9, 0, tzinfo=UTC))
    example_rules["effective_from"] = "2027-01-10"
    publish(service, example_rules)
    ok = service.evaluate(evaluate_body([line(expenseDate="2026-12-11")], submission="2027-01-10"))   # exactly 30 days
    late = service.evaluate(evaluate_body([line(expenseDate="2026-12-10")], submission="2027-01-10"))  # 31 days
    assert ok["ok"] and codes(late) == ["WINDOW_EXPIRED"]


def test_no_window_in_the_rules_means_no_window_check(service, example_rules):
    del example_rules["submission_window_days"]
    publish(service, example_rules)
    assert service.evaluate(evaluate_body([line(expenseDate="2020-01-01")]))["ok"]


def test_a_different_window_is_followed(service, example_rules):
    example_rules["submission_window_days"] = 5
    publish(service, example_rules)
    assert service.evaluate(evaluate_body([line(expenseDate="2026-10-30")]))["ok"]
    assert codes(service.evaluate(evaluate_body([line(expenseDate="2026-10-29")]))) == ["WINDOW_EXPIRED"]


# ---- rules drive everything: change the rules, the answers change -------------------------------------

def test_receipt_threshold_zero_means_every_line_needs_a_receipt(service, example_rules):
    example_rules["receipt_threshold"] = 0
    publish(service, example_rules)
    assert codes(service.evaluate(evaluate_body([line(amount=1, hasReceipt=False)]))) == ["RECEIPT_REQUIRED"]


def test_a_higher_threshold_is_followed(service, example_rules):
    example_rules["receipt_threshold"] = 5000
    publish(service, example_rules)
    assert service.evaluate(evaluate_body([line(amount=4999, category="Other", hasReceipt=False)]))["ok"]
    assert not service.evaluate(evaluate_body([line(amount=5000, category="Other", hasReceipt=False)]))["ok"]


def test_a_different_base_currency(service, example_rules):
    example_rules["base_currency"] = "USD"
    publish(service, example_rules)
    assert service.evaluate(evaluate_body([line(currency="USD", amount=500)]))["ok"]  # base: threshold rule applies
    assert "RECEIPT_REQUIRED" in codes(service.evaluate(evaluate_body([line(currency="INR", amount=5, amountInr=5, hasReceipt=False)])))


def test_a_new_category_needs_no_code_change(service, example_rules):
    example_rules["category_limits"]["Training"] = {"unit": "per_line", "G1": 3000, "G2": 6000, "G3": 9000}
    publish(service, example_rules)
    assert service.evaluate(evaluate_body([line(category="Training", amount=3000)]))["ok"]
    assert codes(service.evaluate(evaluate_body([line(category="Training", amount=3001)]))) == ["LIMIT_EXCEEDED"]


def test_a_new_grade_works(service, example_rules):
    example_rules["grades"].append("G4")
    for lim in example_rules["category_limits"].values():
        lim["G4"] = 10 ** 6
    publish(service, example_rules)
    assert service.evaluate(evaluate_body([line(category="Travel", amount=900000)], grade="G4"))["ok"]


def test_an_extra_tier_is_followed(service, example_rules):
    example_rules["approval_tiers"].insert(1, {"id": "T1b", "max_total": 20000, "steps": ["LINE_MANAGER", "FINANCE_CONTROLLER"]})
    example_rules["approval_tiers"][2]["max_total"] = 60000
    publish(service, example_rules)
    r = service.route(route_body(total=15000, LINE_MANAGER=("a", "G2"), FINANCE_CONTROLLER=("b", "G3")))
    assert r["tier"] == "T1b"


def test_all_sod_checks_off_lets_anything_through(service, example_rules):
    example_rules["segregation_of_duties"] = {k: False for k in example_rules["segregation_of_duties"]}
    publish(service, example_rules)
    r = service.route(route_body(total=20000, submitter="a", grade="G3", payer="a", LINE_MANAGER=("a", "G1"), DEPARTMENT_HEAD=("a", "G1")))
    assert "chain" in r


# ---- route edge cases --------------------------------------------------------------------------------

def test_grade_rank_follows_the_order_in_the_rules(published):
    # G3 submitter, approvers G1/G2: both are below
    for g in ("G1", "G2"):
        r = published.route(route_body(total=5000, submitter="Zed", grade="G3", LINE_MANAGER=("Ravi", g)))
        assert r["blocked"]["code"] == "SOD-4"


def test_ids_are_compared_exactly(published):
    r = published.route(route_body(total=5000, submitter="Ravi", grade="G1", LINE_MANAGER=("ravi", "G2")))
    assert "chain" in r  # "ravi" and "Ravi" are different ids


def test_same_person_in_all_roles_is_caught_at_the_second_step(published):
    r = published.route(route_body(total=20000, LINE_MANAGER=("Ravi", "G2"), DEPARTMENT_HEAD=("Ravi", "G2")))
    assert r["blocked"] == {"code": "SOD-2", "role": "DEPARTMENT_HEAD"}


def test_huge_totals_land_in_the_last_tier(published):
    assert published.route(route_body(total="1e15", FINANCE_CONTROLLER=("f", "G3"), CFO=("c", "G3")))["tier"] == "T4"


def test_route_with_a_total_that_has_cents(published):
    assert published.route(route_body(total="10000.00", LINE_MANAGER=("a", "G2")))["tier"] == "T1"
    assert published.route(route_body(total="10000.01", LINE_MANAGER=("a", "G2"), DEPARTMENT_HEAD=("b", "G3")))["tier"] == "T2"


# ---- caching with clock jumps ---------------------------------------------------------------------------

def test_a_new_version_is_picked_up_within_a_minute_for_future_dates(service, example_rules, clock):
    from datetime import date
    publish(service, example_rules)
    assert service.rules_in_force(date(2026, 12, 15))["version"] == 1  # cached
    example_rules["effective_from"] = "2026-12-01"
    publish(service, example_rules, key="key-00000002")
    assert service.rules_in_force(date(2026, 12, 15))["version"] == 1  # still the cached answer
    clock.advance(seconds=61)
    assert service.rules_in_force(date(2026, 12, 15))["version"] == 2


def test_cache_can_be_switched_off(store, bus, clock, example_rules):
    s = PolicyService(store, bus, clock, cache_ttl=0)
    publish(s, example_rules)
    from datetime import date
    s.rules_in_force(date(2026, 11, 4))
    reads = store.reads
    s.rules_in_force(date(2026, 11, 4))
    assert store.reads == reads + 1


def test_each_service_instance_has_its_own_cache(store, bus, clock, example_rules):
    a, b = PolicyService(store, bus, clock), PolicyService(store, bus, clock)
    publish(a, example_rules)
    from datetime import date
    assert b.rules_in_force(date(2026, 11, 4))["version"] == 1  # b reads through the shared store
