import copy

import pytest

from policy.api import Auth, Request, handle
from tests.policy.conftest import evaluate_body, line, route_body

USER = Auth(kind="jwt", sub="emp1", groups=["employee"])
ADMIN = Auth(kind="jwt", sub="fin1", groups=["finance-admin"])
SUBMIT = Auth(kind="iam", principal="submit")
APPROVE = Auth(kind="iam", principal="approve")


def call(service, method, path, auth=None, body=None, query=None, headers=None):
    return handle(service, Request(method, path, query or {}, headers or {}, body, auth))


# ---- auth rules -------------------------------------------------------------------------------------

@pytest.mark.parametrize("method,path", [("GET", "/v1/policy/rules"), ("GET", "/v1/policy/rules/1"),
                                         ("PUT", "/v1/policy/rules"), ("POST", "/v1/policy/evaluate"),
                                         ("POST", "/v1/policy/route")])
def test_no_identity_is_401(published, method, path):
    assert call(published, method, path).status == 401


def test_public_routes_reject_iam_callers(published):
    assert call(published, "GET", "/v1/policy/rules", SUBMIT).status == 401


@pytest.mark.parametrize("path", ["/v1/policy/evaluate", "/v1/policy/route"])
def test_internal_routes_reject_signed_in_users(published, path):
    assert call(published, "POST", path, USER, {}).status == 403
    assert call(published, "POST", path, ADMIN, {}).status == 403


def test_internal_routes_reject_unknown_callers(published):
    assert call(published, "POST", "/v1/policy/evaluate", Auth(kind="iam", principal="payout"), {}).status == 403


def test_user_without_a_subject_is_401(published):
    assert call(published, "GET", "/v1/policy/rules", Auth(kind="jwt", sub="")).status == 401


# ---- rules routes -----------------------------------------------------------------------------------

def test_get_rules_in_force_defaults_to_today(published):
    r = call(published, "GET", "/v1/policy/rules", USER)
    assert r.status == 200 and r.body["version"] == 1 and r.body["rules"]["base_currency"] == "INR"


def test_get_rules_for_a_date(published):
    assert call(published, "GET", "/v1/policy/rules", USER, query={"effectiveOn": "2026-11-04"}).status == 200
    r = call(published, "GET", "/v1/policy/rules", USER, query={"effectiveOn": "2026-11-03"})
    assert r.status == 404 and r.body["code"] == "NO_RULES_IN_FORCE"


@pytest.mark.parametrize("bad", ["tomorrow", "2026-13-40", "", "20261104"])
def test_bad_effective_on_is_400(published, bad):
    assert call(published, "GET", "/v1/policy/rules", USER, query={"effectiveOn": bad}).status == 400


def test_get_by_version(published):
    assert call(published, "GET", "/v1/policy/rules/1", USER).status == 200
    assert call(published, "GET", "/v1/policy/rules/2", USER).status == 404


def test_put_publishes(service, example_rules):
    r = call(service, "PUT", "/v1/policy/rules", ADMIN, copy.deepcopy(example_rules), headers={"idempotency-key": "key-00000001"})
    assert r.status == 201 and r.body["version"] == 1


def test_put_by_an_employee_is_403(service, example_rules):
    r = call(service, "PUT", "/v1/policy/rules", USER, example_rules, headers={"idempotency-key": "key-00000001"})
    assert r.status == 403 and r.body["code"] == "FORBIDDEN"


def test_put_without_a_key_is_400(service, example_rules):
    assert call(service, "PUT", "/v1/policy/rules", ADMIN, example_rules).status == 400


def test_put_invalid_rules_lists_the_problems(service, example_rules):
    example_rules["grades"] = []
    r = call(service, "PUT", "/v1/policy/rules", ADMIN, example_rules, headers={"idempotency-key": "key-00000001"})
    assert r.status == 422 and r.body["details"]


# ---- evaluate and route routes ---------------------------------------------------------------------

def test_evaluate_ok(published):
    r = call(published, "POST", "/v1/policy/evaluate", SUBMIT, evaluate_body([line()]))
    assert r.status == 200 and r.body["ok"] is True


def test_rule_failure_is_200_not_an_http_error(published):
    r = call(published, "POST", "/v1/policy/evaluate", SUBMIT, evaluate_body([line(amount=2000)]))
    assert r.status == 200 and r.body["ok"] is False


def test_evaluate_without_rules_is_404(service):
    r = call(service, "POST", "/v1/policy/evaluate", SUBMIT, evaluate_body([line()]))
    assert r.status == 404 and r.body["code"] == "NO_RULES_IN_FORCE"


def test_evaluate_bad_body_is_400(published):
    assert call(published, "POST", "/v1/policy/evaluate", SUBMIT, {"lines": []}).status == 400
    assert call(published, "POST", "/v1/policy/evaluate", SUBMIT, None).status == 400


def test_route_ok_and_blocked(published):
    people = dict(LINE_MANAGER=("Ravi", "G2"))
    ok = call(published, "POST", "/v1/policy/route", APPROVE, route_body(total=5000, **people))
    assert ok.status == 200 and ok.body["chain"]
    blocked = call(published, "POST", "/v1/policy/route", APPROVE, route_body(total=5000, submitter="Ravi", grade="G2", **people))
    assert blocked.status == 200 and blocked.body["blocked"]["code"] == "SOD-1"


# ---- plumbing --------------------------------------------------------------------------------------

def test_unknown_route_is_404(published):
    assert call(published, "GET", "/v2/nothing", USER).status == 404


@pytest.mark.parametrize("method,path,allow", [("DELETE", "/v1/policy/rules", "GET, PUT"),
                                               ("POST", "/v1/policy/rules/1", "GET"),
                                               ("GET", "/v1/policy/evaluate", "POST"),
                                               ("PUT", "/v1/policy/route", "POST")])
def test_wrong_method_is_405(published, method, path, allow):
    r = call(published, method, path, USER)
    assert r.status == 405 and r.headers["allow"] == allow


def test_trailing_slash_is_tolerated(published):
    assert call(published, "GET", "/v1/policy/rules/", USER).status == 200


def test_method_is_case_insensitive(published):
    assert call(published, "get", "/v1/policy/rules", USER).status == 200


def test_request_id_is_echoed(published):
    r = call(published, "GET", "/v1/policy/rules", USER, headers={"x-request-id": "abc-123"})
    assert r.headers["x-request-id"] == "abc-123"


def test_unexpected_errors_are_500_without_details(published, monkeypatch):
    monkeypatch.setattr(published, "rules_in_force", lambda on: 1 / 0)
    r = call(published, "GET", "/v1/policy/rules", USER)
    assert r.status == 500 and r.body == {"code": "INTERNAL", "message": "Something went wrong"}


def test_error_bodies_match_the_contract(published):
    r = call(published, "GET", "/v1/policy/rules", USER, query={"effectiveOn": "x"})
    assert set(r.body) <= {"code", "message", "details"} and {"code", "message"} <= set(r.body)
