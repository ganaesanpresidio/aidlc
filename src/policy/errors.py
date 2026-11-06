from __future__ import annotations


class PolicyError(Exception):
    """A request problem, mapped to an HTTP status by the API layer."""

    def __init__(self, status: int, code: str, message: str, details: list[str] | None = None) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details or []

    def body(self) -> dict:
        out = {"code": self.code, "message": self.message}
        if self.details:
            out["details"] = self.details
        return out


class NoRulesInForce(PolicyError):
    def __init__(self, on: str) -> None:
        super().__init__(404, "NO_RULES_IN_FORCE", f"No rules are in force on {on}")


class VersionExists(Exception):
    """Raised by a store when a rules version already exists (versions are immutable)."""
