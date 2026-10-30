"""Load settings from the project's .env file and the environment.

Real values live in `.env` (git-ignored). `env.example` lists every key.
A variable already set in the environment wins over the same key in `.env`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


def load_env_file(path: Path = ENV_FILE) -> dict[str, str]:
    """Parse KEY=VALUE lines. Ignores blanks and comments; never executes anything."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def get(key: str, default: str = "", env_file: Path = ENV_FILE) -> str:
    """Environment first, then .env, then the default."""
    if os.environ.get(key):
        return os.environ[key]
    return load_env_file(env_file).get(key) or default


@dataclass(frozen=True)
class JiraSettings:
    mcp_url: str
    base_url: str
    cloud_id: str
    project_key: str
    epic_key: str
    email: str
    api_token: str

    def missing(self) -> list[str]:
        """Names of the settings needed to reach the Jira project that are still empty."""
        required = {
            "JIRA_BASE_URL": self.base_url,
            "JIRA_PROJECT_KEY": self.project_key,
        }
        return [name for name, value in required.items() if not value]

    def masked(self) -> dict[str, str]:
        """Safe to print: the API token is never shown."""
        return {
            "ATLASSIAN_MCP_URL": self.mcp_url,
            "JIRA_BASE_URL": self.base_url,
            "JIRA_CLOUD_ID": self.cloud_id,
            "JIRA_PROJECT_KEY": self.project_key,
            "JIRA_EPIC_KEY": self.epic_key,
            "JIRA_EMAIL": self.email,
            "JIRA_API_TOKEN": "set" if self.api_token else "",
        }


def jira_settings(env_file: Path = ENV_FILE) -> JiraSettings:
    return JiraSettings(
        mcp_url=get("ATLASSIAN_MCP_URL", "https://mcp.atlassian.com/v1/mcp", env_file),
        base_url=get("JIRA_BASE_URL", "", env_file).rstrip("/"),
        cloud_id=get("JIRA_CLOUD_ID", "", env_file),
        project_key=get("JIRA_PROJECT_KEY", "", env_file),
        epic_key=get("JIRA_EPIC_KEY", "", env_file),
        email=get("JIRA_EMAIL", "", env_file),
        api_token=get("JIRA_API_TOKEN", "", env_file),
    )
