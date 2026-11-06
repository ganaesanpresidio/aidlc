import sys

from aidlc_e2e.config import ENV_FILE, aws_settings, jira_settings


def main() -> None:
    """`uv run aidlc-e2e [check]` — show the Jira settings (token masked); `check` also tests the connection; `publish [title-text]` creates the mock policy and approval matrix pages in Confluence; `serve policy|submit` runs a unit locally (mock backend); `demo` prints one full journey; `design` validates OpenAPI and event schemas; `rules` validates the policy rules config and routes sample claims.

    Use another env file with AIDLC_ENV_FILE, e.g. `AIDLC_ENV_FILE=env.dev uv run aidlc-e2e check`.
    """
    if sys.argv[1:2] == ["serve"]:
        from aidlc_e2e.local import serve

        serve(sys.argv[2] if len(sys.argv) > 2 else "", int(sys.argv[3]) if len(sys.argv) > 3 else None)
        return
    if sys.argv[1:2] == ["demo"]:
        from aidlc_e2e.local import demo

        demo()
        return
    if sys.argv[1:2] == ["design"]:
        from aidlc_e2e.design_check import run as run_design

        sys.exit(0 if run_design() else 1)
    if sys.argv[1:2] == ["rules"]:
        from aidlc_e2e.rules_check import run

        sys.exit(0 if run() else 1)
    if sys.argv[1:2] == ["publish"]:
        from aidlc_e2e.confluence import publish

        sys.exit(0 if publish(sys.argv[2] if len(sys.argv) > 2 else "") else 1)
    settings = jira_settings()
    source = ENV_FILE if ENV_FILE.is_file() else f"environment only ({ENV_FILE.name} not found)"
    print(f"Jira settings from: {source}")
    for key, value in settings.masked().items():
        print(f"  {key:<20} {value or '-'}")
    print("AWS settings:")
    for key, value in aws_settings().masked().items():
        print(f"  {key:<22} {value or '-'}")
    if missing := settings.missing():
        print(f"Missing: {', '.join(missing)}. Add them to {ENV_FILE.name} (see env.example).")
        sys.exit(1)
    print(f"Project: {settings.base_url}/browse/{settings.project_key}")
    if sys.argv[1:2] == ["check"]:
        from aidlc_e2e.connectivity import check_all

        print("Connectivity:")
        sys.exit(0 if check_all(settings) else 1)
