import sys

from aidlc_e2e.config import ENV_FILE, jira_settings


def main() -> None:
    """`uv run aidlc-e2e [check]` — show the Jira settings (token masked); `check` also tests the connection.

    Use another env file with AIDLC_ENV_FILE, e.g. `AIDLC_ENV_FILE=env.dev uv run aidlc-e2e check`.
    """
    settings = jira_settings()
    source = ENV_FILE if ENV_FILE.is_file() else f"environment only ({ENV_FILE.name} not found)"
    print(f"Jira settings from: {source}")
    for key, value in settings.masked().items():
        print(f"  {key:<20} {value or '-'}")
    if missing := settings.missing():
        print(f"Missing: {', '.join(missing)}. Add them to {ENV_FILE.name} (see env.example).")
        sys.exit(1)
    print(f"Project: {settings.base_url}/browse/{settings.project_key}")
    if sys.argv[1:2] == ["check"]:
        from aidlc_e2e.connectivity import check_all

        print("Connectivity:")
        sys.exit(0 if check_all(settings) else 1)
