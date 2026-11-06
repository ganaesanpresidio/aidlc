"""How submit asks the policy unit. In mock mode it calls the policy code in the same process, through its real API layer."""

from __future__ import annotations

from typing import Any, Protocol

from submit.errors import PolicyRejected, PolicyUnavailable


class PolicyClient(Protocol):
    def evaluate(self, body: dict[str, Any]) -> dict[str, Any]: ...


class InProcessPolicyClient:
    """Mock backend: goes through policy.api.handle with an internal `submit` identity, like the real call would."""

    def __init__(self, policy_service) -> None:
        self._svc = policy_service
        self.down = False  # tests flip this to prove submit fails closed

    def evaluate(self, body: dict[str, Any]) -> dict[str, Any]:
        from policy.api import Auth, Request, handle

        if self.down:
            raise PolicyUnavailable("policy is down")
        resp = handle(self._svc, Request("POST", "/v1/policy/evaluate", body=body, auth=Auth(kind="iam", principal="submit")))
        return _interpret(resp.status, resp.body)


def _interpret(status: int, body: Any) -> dict[str, Any]:
    if status == 200:
        return body
    if status == 400 and isinstance(body, dict):
        raise PolicyRejected(body.get("code", "INVALID_REQUEST"), body.get("message", "policy refused the request"))
    raise PolicyUnavailable(f"policy answered {status}")  # 404 no rules, 5xx, anything unexpected: fail closed


class HttpPolicyClient:
    """Real call to the internal policy URL, signed with the caller's IAM identity (SigV4). UNVERIFIED against AWS."""

    def __init__(self, base_url: str, region: str, session=None, timeout: float = 3.0) -> None:
        self._base, self._region, self._timeout, self._session = base_url.rstrip("/"), region, timeout, session

    def evaluate(self, body: dict[str, Any]) -> dict[str, Any]:
        import json

        import boto3
        import requests
        from botocore.auth import SigV4Auth
        from botocore.awsrequest import AWSRequest

        url = f"{self._base}/v1/policy/evaluate"
        data = json.dumps(body)
        creds = (self._session or boto3.Session()).get_credentials()
        req = AWSRequest(method="POST", url=url, data=data, headers={"content-type": "application/json"})
        SigV4Auth(creds, "execute-api", self._region).add_auth(req)
        try:
            resp = requests.post(url, data=data, headers=dict(req.headers), timeout=self._timeout)
        except requests.RequestException as exc:
            raise PolicyUnavailable(type(exc).__name__) from exc
        try:
            payload = resp.json()
        except ValueError:
            payload = None
        return _interpret(resp.status_code, payload)
