"""Publish repo markdown pages to the Confluence design space (create only, never overwrites).

`uv run aidlc-e2e publish` uses the REST API with JIRA_EMAIL + JIRA_API_TOKEN from the env file.
The token is never printed.
"""

from __future__ import annotations

import re
import sys

import markdown
import requests

from aidlc_e2e.config import PROJECT_ROOT, jira_settings

TIMEOUT = 20
INCEPTION = PROJECT_ROOT / "aidlc-docs" / "inception"

# (title, source file). Titles start with a fixed prefix so the pages are easy to find.
PAGES = [
    ("AIDLC · Mock expense policy (MOCK DATA)", INCEPTION / "mock-expense-policy.md"),
    ("AIDLC · Approval matrix (MOCK DATA)", INCEPTION / "approval-matrix.md"),
]


def to_storage(path) -> str:
    text = re.sub(r"\A---\n.*?\n---\n", "", path.read_text(), flags=re.S)
    text = re.sub(r"^# .*\n", "", text, count=1, flags=re.M)  # page title carries the H1
    text = re.sub(r"\[([^\]]+)\]\((?!https?:)[^)]*\)", r"\1", text)  # repo-relative links are not valid here
    html = markdown.markdown(text, extensions=["tables", "fenced_code"])
    return html + "<p><em>Source: aidlc-docs/inception/" + path.name + " in the repo. Edit there.</em></p>"


def publish() -> bool:
    s = jira_settings()
    auth = (s.email, s.api_token)
    base = f"{s.base_url}/wiki/api/v2"
    r = requests.get(f"{base}/spaces", params={"keys": s.confluence_space_key}, auth=auth, timeout=TIMEOUT)
    if not r.ok or not r.json().get("results"):
        print(f"FAIL  space {s.confluence_space_key}: HTTP {r.status_code}")
        return False
    space_id = r.json()["results"][0]["id"]
    ok = True
    for title, path in PAGES:
        q = requests.get(f"{base}/spaces/{space_id}/pages", params={"title": title}, auth=auth, timeout=TIMEOUT)
        if q.ok and q.json().get("results"):
            print(f"SKIP  exists: {title}")
            continue
        body = {"spaceId": space_id, "status": "current", "title": title,
                "body": {"representation": "storage", "value": to_storage(path)}}
        c = requests.post(f"{base}/pages", json=body, auth=auth, timeout=TIMEOUT)
        if c.ok:
            print(f"OK    {title}: {s.base_url}/wiki{c.json()['_links']['webui']}")
        else:
            print(f"FAIL  {title}: HTTP {c.status_code} {c.text[:200]}")
            ok = False
    return ok


if __name__ == "__main__":
    sys.exit(0 if publish() else 1)
