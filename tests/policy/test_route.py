import pytest

from policy.errors import PolicyError
from tests.policy.conftest import route_body

ALL = dict(LINE_MANAGER=("Ravi", "G2"), DEPARTMENT_HEAD=("Dev", "G3"), FINANCE_CONTROLLER=("Fin", "G3"), CFO=("Cee", "G3"))


def chain(result):
    return [(c["role"], c["approver"]) for c in result["chain"]]


# ---- tier boundaries (A6, ADR-003) ---------------------------------------------------------------

@pytest.mark.parametrize("total,tier", [
    (1, "T1"), (10000, "T1"), (10000.01, "T2"), (10001, "T2"), (50000, "T2"), (50001, "T3"),
    (200000, "T3"), (200000.01, "T4"), (200001, "T4"), (5_000_000, "T4")])
def test_tier_boundaries(published, total, tier):
    assert published.route(route_body(total=total, **ALL))["tier"] == tier


def test_chains_per_tier(published):
    assert chain(published.route(route_body(total=5000, **ALL))) == [("LINE_MANAGER", "Ravi")]
    assert chain(published.route(route_body(total=20000, **ALL))) == [("LINE_MANAGER", "Ravi"), ("DEPARTMENT_HEAD", "Dev")]
    assert chain(published.route(route_body(total=100000, **ALL))) == [("DEPARTMENT_HEAD", "Dev"), ("FINANCE_CONTROLLER", "Fin")]
    assert chain(published.route(route_body(total=300000, **ALL))) == [("FINANCE_CONTROLLER", "Fin"), ("CFO", "Cee")]


# ---- exception approver --------------------------------------------------------------------------

def test_exception_adds_finance_controller(published):
    r = published.route(route_body(total=5000, exception=True, **ALL))
    assert chain(r) == [("LINE_MANAGER", "Ravi"), ("FINANCE_CONTROLLER", "Fin")]


def test_exception_does_not_duplicate_finance_controller(published):
    r = published.route(route_body(total=100000, exception=True, **ALL))
    assert chain(r) == [("DEPARTMENT_HEAD", "Dev"), ("FINANCE_CONTROLLER", "Fin")]


def test_exception_needs_a_finance_controller_holder(published):
    people = {k: v for k, v in ALL.items() if k != "FINANCE_CONTROLLER"}
    r = published.route(route_body(total=5000, exception=True, **people))
    assert r["blocked"] == {"code": "MISSING_ROLE_HOLDER", "role": "FINANCE_CONTROLLER"}


# ---- segregation of duties -------------------------------------------------------------------------

def test_sod1_submitter_is_the_approver(published):
    r = published.route(route_body(total=5000, submitter="Ravi", grade="G2", LINE_MANAGER=("Ravi", "G2")))
    assert r["blocked"] == {"code": "SOD-1", "role": "LINE_MANAGER"} and "chain" not in r


def test_sod1_in_the_second_step(published):
    people = dict(ALL, DEPARTMENT_HEAD=("Asha", "G3"))
    r = published.route(route_body(total=20000, **people))
    assert r["blocked"] == {"code": "SOD-1", "role": "DEPARTMENT_HEAD"}


def test_sod2_same_person_in_two_steps(published):
    people = dict(ALL, DEPARTMENT_HEAD=("Ravi", "G3"))
    r = published.route(route_body(total=20000, **people))
    assert r["blocked"] == {"code": "SOD-2", "role": "DEPARTMENT_HEAD"}


def test_sod3_payer_is_the_approver(published):
    r = published.route(route_body(total=5000, payer="Ravi", **ALL))
    assert r["blocked"] == {"code": "SOD-3", "role": "LINE_MANAGER"}


def test_no_payer_means_no_sod3_check(published):
    assert "chain" in published.route(route_body(total=5000, **ALL))


def test_sod4_approver_grade_below_submitter(published):
    r = published.route(route_body(total=5000, submitter="Zed", grade="G3", LINE_MANAGER=("Ravi", "G2")))
    assert r["blocked"] == {"code": "SOD-4", "role": "LINE_MANAGER"}


def test_sod4_equal_grade_is_allowed(published):
    r = published.route(route_body(total=5000, submitter="Zed", grade="G2", LINE_MANAGER=("Ravi", "G2")))
    assert "chain" in r


def test_checks_run_in_order_first_failure_wins(published):
    # Ravi is the submitter (SOD-1), also the payer (SOD-3) and below grade (SOD-4): SOD-1 is reported
    r = published.route(route_body(total=5000, submitter="Ravi", grade="G3", payer="Ravi", LINE_MANAGER=("Ravi", "G1")))
    assert r["blocked"]["code"] == "SOD-1"


def test_blocked_result_still_names_the_tier(published):
    r = published.route(route_body(total=20000, submitter="Ravi", grade="G2", **ALL))
    assert r["tier"] == "T2"


def test_missing_role_holder(published):
    r = published.route(route_body(total=20000, LINE_MANAGER=("Ravi", "G2")))
    assert r["blocked"] == {"code": "MISSING_ROLE_HOLDER", "role": "DEPARTMENT_HEAD"}


def test_extra_role_holders_are_ignored(published):
    assert len(published.route(route_body(total=5000, **ALL))["chain"]) == 1


def test_sod_flags_can_be_switched_off_by_rules(service, example_rules):
    example_rules["segregation_of_duties"]["no_self_approval"] = False
    service.publish(example_rules, actor="f", groups=["finance-admin"], idempotency_key="key-00000002")
    r = service.route(route_body(total=5000, submitter="Ravi", grade="G2", LINE_MANAGER=("Ravi", "G2")))
    assert "chain" in r  # rules drive the checks, not code


# ---- rules version ---------------------------------------------------------------------------------

def test_route_reports_rules_version(published):
    assert published.route(route_body(total=5000, **ALL))["rulesVersion"] == 1


def test_route_with_an_explicit_version(published, clock, example_rules):
    example_rules["effective_from"] = "2026-12-01"
    example_rules["approval_tiers"][0]["max_total"] = 1000  # v2 is stricter
    published.publish(example_rules, actor="f", groups=["finance-admin"], idempotency_key="key-00000003")
    body = route_body(total=5000, **ALL)
    assert published.route(dict(body, rulesVersion=1))["tier"] == "T1"
    assert published.route(dict(body, rulesVersion=2))["tier"] == "T2"


@pytest.mark.parametrize("v", [0, -1, "1", 1.5, True])
def test_bad_rules_version(published, v):
    with pytest.raises(PolicyError) as e:
        published.route(dict(route_body(total=5000, **ALL), rulesVersion=v))
    assert e.value.status == 400


def test_unknown_rules_version(published):
    with pytest.raises(PolicyError) as e:
        published.route(dict(route_body(total=5000, **ALL), rulesVersion=99))
    assert e.value.status == 404


# ---- request errors --------------------------------------------------------------------------------

@pytest.mark.parametrize("mutate,code", [
    (lambda b: b.update(claimRef=""), "INVALID_REQUEST"),
    (lambda b: b.update(submitter=None), "INVALID_REQUEST"),
    (lambda b: b.update(grade="G7"), "UNKNOWN_GRADE"),
    (lambda b: b.update(totalInr=0), "INVALID_REQUEST"),
    (lambda b: b.update(totalInr=-1), "INVALID_REQUEST"),
    (lambda b: b.update(totalInr="lots"), "INVALID_REQUEST"),
    (lambda b: b.update(requiresException="no"), "INVALID_REQUEST"),
    (lambda b: b.update(payer=""), "INVALID_REQUEST"),
    (lambda b: b.update(roleHolders=[]), "INVALID_REQUEST"),
    (lambda b: b["roleHolders"].update(JANITOR={"id": "x", "grade": "G1"}), "INVALID_REQUEST"),
    (lambda b: b["roleHolders"]["LINE_MANAGER"].update(id=""), "INVALID_REQUEST"),
    (lambda b: b["roleHolders"]["LINE_MANAGER"].update(grade="G9"), "UNKNOWN_GRADE"),
    (lambda b: b["roleHolders"].update(LINE_MANAGER="Ravi"), "INVALID_REQUEST"),
])
def test_bad_requests_are_400(published, mutate, code):
    body = route_body(total=5000, **ALL)
    mutate(body)
    with pytest.raises(PolicyError) as e:
        published.route(body)
    assert e.value.status == 400 and e.value.code == code


def test_body_must_be_an_object(published):
    with pytest.raises(PolicyError):
        published.route("x")


# ---- property: a routed chain is always safe -------------------------------------------------------

def test_chain_never_has_the_submitter_a_repeat_or_a_lower_grade(published):
    people_pool = [("Ravi", "G2"), ("Dev", "G3"), ("Fin", "G3"), ("Cee", "G3"), ("Asha", "G1"), ("Zed", "G3")]
    grades = {"G1": 0, "G2": 1, "G3": 2}
    checked = 0
    for submitter, sgrade in people_pool:
        for total in (1, 10000, 10001, 50001, 200001):
            for exc in (False, True):
                for i in range(len(people_pool)):
                    roles = ["LINE_MANAGER", "DEPARTMENT_HEAD", "FINANCE_CONTROLLER", "CFO"]
                    h = dict(zip(roles, [people_pool[(i + k) % 6] for k in range(4)], strict=True))
                    r = published.route(route_body(total=total, submitter=submitter, grade=sgrade, exception=exc, **h))
                    if "chain" not in r:
                        continue
                    checked += 1
                    who = [c["approver"] for c in r["chain"]]
                    assert submitter not in who and len(set(who)) == len(who)
                    assert all(grades[dict(people_pool)[w]] >= grades[sgrade] for w in who)
    assert checked > 50  # the loop really exercised safe chains
