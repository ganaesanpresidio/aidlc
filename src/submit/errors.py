from __future__ import annotations


class SubmitError(Exception):
    def __init__(self, status: int, code: str, message: str, details: list[dict] | None = None) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details or []

    def body(self) -> dict:
        out: dict = {"code": self.code, "message": self.message}
        if self.details:
            out["details"] = self.details
        return out


def not_found(what: str = "Claim") -> SubmitError:
    # Other people's claims look exactly like missing ones (X4)
    return SubmitError(404, "NOT_FOUND", f"{what} not found")


class ConditionFailed(Exception):
    """A table write condition was not met (item exists, or version changed)."""


class PolicyUnavailable(Exception):
    """The policy unit could not answer. Submit fails closed."""


class PolicyRejected(Exception):
    """The policy unit refused the request itself (HTTP 400)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
