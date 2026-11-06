import pytest

from policy.errors import NoRulesInForce, PolicyError
from tests.policy.conftest import evaluate_body, line


def codes(result):
    return [(v["lineId"], v["code"]) for v in result["violations"]]


# ---- receipt rule: boundary at 1,000 INR (Q16, Q17) -------------------------------------------

@pytest.mark.parametrize("amount,needs", [
    (999.99, False), (999, False), (1000, True), (1000.00, True), (1000.01, True), (5000, True)])
def test_receipt_threshold_boundary(published, amount, needs):
    r = published.evaluate(evaluate_body([line(amount=amount, category="Other", hasReceipt=False)]))
    assert ("L1", "RECEIPT_REQUIRED") in codes(r) if needs else r["ok"]


def test_receipt_present_satisfies_the_rule(published):
    assert published.evaluate(evaluate_body([line(amount=1200, category="Other", hasReceipt=True)]))["ok"]


@pytest.mark.parametrize("amount", [1, 50, 999.99, 5000])
def test_foreign_currency_always_needs_receipt(published, amount):
    r = published.evaluate(evaluate_body([line(amount=amount, currency="USD", amountInr=100,
                                               category="Other", hasReceipt=False)]))
    assert ("L1", "RECEIPT_REQUIRED") in codes(r)


# ---- category limits ---------------------------------------------------------------------------

@pytest.mark.parametrize("grade,cat,amount,ok", [
    ("G1", "Meals", 1500, True), ("G1", "Meals", 1500.01, False), ("G2", "Meals", 2500, True),
    ("G2", "Meals", 2501, False), ("G3", "Meals", 4000, True), ("G3", "Meals", 4001, False),
    ("G1", "Travel", 25000, True), ("G1", "Travel", 25001, False), ("G3", "Travel", 100000, True),
    ("G1", "Other", 5000, True), ("G1", "Other", 5000.5, False), ("G3", "Other", 20000, True)])
def test_per_line_and_per_day_limits(published, grade, cat, amount, ok):
    r = published.evaluate(evaluate_body([line(category=cat, amount=amount)], grade=grade))
    assert r["ok"] is ok
    if not ok:
        assert codes(r) == [("L1", "LIMIT_EXCEEDED")]


def test_limit_exceeded_reports_the_cap(published):
    r = published.evaluate(evaluate_body([line(category="Meals", amount=2000)]))
    assert r["violations"] == [{"lineId": "L1", "code": "LIMIT_EXCEEDED", "limit": 1500}]


def test_per_night_limit_scales_with_nights(published):
    ok = published.evaluate(evaluate_body([line(category="Accommodation", amount=18000, quantity=3)]))
    assert ok["ok"]
    bad = published.evaluate(evaluate_body([line(category="Accommodation", amount=18001, quantity=3)]))
    assert codes(bad) == [("L1", "LIMIT_EXCEEDED")] and bad["violations"][0]["limit"] == 18000


def test_per_night_defaults_to_one_night(published):
    assert published.evaluate(evaluate_body([line(category="Accommodation", amount=6000)]))["ok"]
    assert not published.evaluate(evaluate_body([line(category="Accommodation", amount=6001)]))["ok"]


def test_per_day_meals_scale_with_days(published):
    assert published.evaluate(evaluate_body([line(category="Meals", amount=4500, quantity=3)]))["ok"]
    assert not published.evaluate(evaluate_body([line(category="Meals", amount=4501, quantity=3)]))["ok"]


def test_mileage_is_rate_times_km(published):
    assert published.evaluate(evaluate_body([line(category="Mileage", amount=1200, quantity=100)]))["ok"]
    r = published.evaluate(evaluate_body([line(category="Mileage", amount=1201, quantity=100)]))
    assert codes(r) == [("L1", "LIMIT_EXCEEDED")]


@pytest.mark.parametrize("qty", [None, 0])
def test_mileage_needs_a_distance(published, qty):
    r = published.evaluate(evaluate_body([line(category="Mileage", amount=100, quantity=qty)]))
    assert codes(r) == [("L1", "INVALID_QUANTITY")]


def test_zero_nights_is_invalid(published):
    r = published.evaluate(evaluate_body([line(category="Accommodation", amount=100, quantity=0)]))
    assert codes(r) == [("L1", "INVALID_QUANTITY")]


def test_unknown_category(published):
    r = published.evaluate(evaluate_body([line(category="Yacht", amount=10)]))
    assert codes(r) == [("L1", "UNKNOWN_CATEGORY")]


# ---- exceptions (A3) ---------------------------------------------------------------------------

def test_exception_reason_allows_over_limit_and_flags_it(published):
    r = published.evaluate(evaluate_body([line(category="Meals", amount=2000, exceptionReason="client dinner")]))
    assert r["ok"] and r["requiresException"] is True


@pytest.mark.parametrize("reason", ["", "   ", "\n\t"])
def test_blank_exception_reason_does_not_count(published, reason):
    r = published.evaluate(evaluate_body([line(category="Meals", amount=2000, exceptionReason=reason)]))
    assert codes(r) == [("L1", "LIMIT_EXCEEDED")] and r["requiresException"] is False


def test_exception_reason_on_a_line_within_limit_is_not_an_exception(published):
    r = published.evaluate(evaluate_body([line(amount=500, exceptionReason="just in case")]))
    assert r["ok"] and r["requiresException"] is False


def test_exception_does_not_hide_a_missing_receipt(published):
    r = published.evaluate(evaluate_body([line(category="Meals", amount=2000, exceptionReason="x", hasReceipt=False)]))
    assert codes(r) == [("L1", "RECEIPT_REQUIRED")]


# ---- submission window (A5) ------------------------------------------------------------------

@pytest.mark.parametrize("expense,expired", [
    ("2026-11-04", False), ("2026-10-05", False), ("2026-10-04", True), ("2026-09-01", True)])
def test_window_is_30_days(published, expense, expired):
    r = published.evaluate(evaluate_body([line(expenseDate=expense)]))
    assert (("L1", "WINDOW_EXPIRED") in codes(r)) is expired


def test_future_dated_expense(published):
    r = published.evaluate(evaluate_body([line(expenseDate="2026-11-05")]))
    assert codes(r) == [("L1", "FUTURE_DATE_EXPENSE")]


# ---- non-INR lines (Q40) -----------------------------------------------------------------------

def test_foreign_line_needs_inr_equivalent(published):
    r = published.evaluate(evaluate_body([line(currency="USD", amount=20, category="Meals")]))
    assert ("L1", "MISSING_INR_EQUIVALENT") in codes(r)


def test_foreign_line_limit_uses_the_inr_equivalent(published):
    r = published.evaluate(evaluate_body([line(currency="USD", amount=20, amountInr=1400, category="Meals")]))
    assert r["ok"]
    r = published.evaluate(evaluate_body([line(currency="USD", amount=20, amountInr=1600, category="Meals")]))
    assert codes(r) == [("L1", "LIMIT_EXCEEDED")]


# ---- several lines, ordering, result shape -----------------------------------------------------

def test_each_line_is_judged_separately(published):
    r = published.evaluate(evaluate_body([
        line(lineId="A", amount=100), line(lineId="B", category="Meals", amount=2000),
        line(lineId="C", category="Other", amount=2000, hasReceipt=False)]))
    assert codes(r) == [("B", "LIMIT_EXCEEDED"), ("C", "RECEIPT_REQUIRED")]


def test_one_line_can_have_several_violations(published):
    r = published.evaluate(evaluate_body([line(category="Meals", amount=2000, hasReceipt=False,
                                               expenseDate="2026-09-01")]))
    assert {c for _, c in codes(r)} == {"WINDOW_EXPIRED", "LIMIT_EXCEEDED", "RECEIPT_REQUIRED"}


def test_result_carries_rules_version(published):
    assert published.evaluate(evaluate_body([line()]))["rulesVersion"] == 1


def test_money_is_exact_not_float(published):
    # 0.1 + 0.2 style errors must not move a line across the 1,000 threshold
    r = published.evaluate(evaluate_body([line(amount="999.99", category="Other", hasReceipt=False)]))
    assert r["ok"]
    r = published.evaluate(evaluate_body([line(amount="1000.00", category="Other", hasReceipt=False)]))
    assert not r["ok"]


# ---- the rules in force are chosen by submission date ---------------------------------------------

def test_no_rules_on_that_date(published):
    with pytest.raises(NoRulesInForce):
        published.evaluate(evaluate_body([line()], submission="2026-11-03"))


# ---- request errors ----------------------------------------------------------------------------

@pytest.mark.parametrize("mutate,code", [
    (lambda b: b.update(grade="G9"), "UNKNOWN_GRADE"),
    (lambda b: b.update(grade=None), "UNKNOWN_GRADE"),
    (lambda b: b.update(submissionDate="04/11/2026"), "INVALID_DATE"),
    (lambda b: b.update(submissionDate=None), "INVALID_DATE"),
    (lambda b: b.update(lines=[]), "INVALID_REQUEST"),
    (lambda b: b.update(lines="nope"), "INVALID_REQUEST"),
    (lambda b: b.update(lines=["x"]), "INVALID_REQUEST"),
    (lambda b: b["lines"][0].update(amount=0), "INVALID_REQUEST"),
    (lambda b: b["lines"][0].update(amount=-5), "INVALID_REQUEST"),
    (lambda b: b["lines"][0].update(amount="abc"), "INVALID_REQUEST"),
    (lambda b: b["lines"][0].update(amount=True), "INVALID_REQUEST"),
    (lambda b: b["lines"][0].update(amount=float("nan")), "INVALID_REQUEST"),
    (lambda b: b["lines"][0].update(amount=float("inf")), "INVALID_REQUEST"),
    (lambda b: b["lines"][0].update(currency="rupees"), "INVALID_REQUEST"),
    (lambda b: b["lines"][0].update(currency=None), "INVALID_REQUEST"),
    (lambda b: b["lines"][0].update(expenseDate="2026-02-30"), "INVALID_DATE"),
    (lambda b: b["lines"][0].update(hasReceipt="yes"), "INVALID_REQUEST"),
    (lambda b: b["lines"][0].update(lineId=""), "INVALID_REQUEST"),
    (lambda b: b["lines"][0].update(category=""), "INVALID_REQUEST"),
    (lambda b: b["lines"][0].update(quantity=-1), "INVALID_REQUEST"),
    (lambda b: b["lines"][0].update(amountInr=0), "INVALID_REQUEST"),
    (lambda b: b["lines"][0].update(exceptionReason=5), "INVALID_REQUEST"),
])
def test_bad_requests_are_400(published, mutate, code):
    body = evaluate_body([line()])
    mutate(body)
    with pytest.raises(PolicyError) as e:
        published.evaluate(body)
    assert e.value.status == 400 and e.value.code == code


def test_repeated_line_ids_rejected(published):
    with pytest.raises(PolicyError) as e:
        published.evaluate(evaluate_body([line(), line()]))
    assert e.value.status == 400


def test_body_must_be_an_object(published):
    with pytest.raises(PolicyError):
        published.evaluate([1])


def test_evaluate_changes_nothing(published, store, bus):
    before = len(bus.events)
    published.evaluate(evaluate_body([line(amount=2000)]))
    assert len(bus.events) == before
