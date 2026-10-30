import sys

from aidlc_e2e.config import ENV_FILE, jira_settings


def main() -> None:
    """`uv run aidlc-e2e` — show the Jira settings loaded from .env (token masked)."""
    settings = jira_settings()
    source = ENV_FILE if ENV_FILE.is_file() else "environment only (no .env file found)"
    print(f"Jira settings from: {source}")
    for key, value in settings.masked().items():
        print(f"  {key:<18} {value or '-'}")
    if missing := settings.missing():
        print(f"Missing: {', '.join(missing)}. Add them to .env (see env.example).")
        sys.exit(1)
    print(f"Project: {settings.base_url}/browse/{settings.project_key}")
