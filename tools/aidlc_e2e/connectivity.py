"""Check that the Jira and Confluence settings can reach the Atlassian site.

Uses the REST API with basic auth (JIRA_EMAIL + JIRA_API_TOKEN). Read-only GETs.
The token is never printed.
"""

from __future__ import annotations

import requests

from aidlc_e2e.config import JiraSettings

TIMEOUT = 15


def _get(settings: JiraSettings, path: str) -> requests.Response:
    return requests.get(
        f"{settings.base_url}{path}",
        auth=(settings.email, settings.api_token),
        headers={"Accept": "application/json"},
        timeout=TIMEOUT,
    )


def _check(label: str, settings: JiraSettings, path: str, describe) -> bool:
    try:
        resp = _get(settings, path)
    except requests.RequestException as exc:
        print(f"  FAIL  {label}: {type(exc).__name__}")
        return False
    if resp.ok:
        print(f"  OK    {label}: {describe(resp.json())}")
        return True
    print(f"  FAIL  {label}: HTTP {resp.status_code}")
    return False


def check_all(settings: JiraSettings) -> bool:
    if not (settings.email and settings.api_token):
        print("  FAIL  JIRA_EMAIL and JIRA_API_TOKEN are both needed for the REST check.")
        return False
    results = [
        _check("Jira sign-in", settings, "/rest/api/3/myself",
               lambda j: f"signed in as {j.get('displayName', '?')}"),
        _check(f"Jira project {settings.project_key}", settings,
               f"/rest/api/3/project/{settings.project_key}",
               lambda j: f"{j.get('name', '?')} ({j.get('projectTypeKey', '?')})"),
    ]
    if settings.epic_key:
        results.append(_check(f"Jira epic {settings.epic_key}", settings,
                              f"/rest/api/3/issue/{settings.epic_key}?fields=summary,issuetype",
                              lambda j: f"{j['fields']['issuetype']['name']}: {j['fields']['summary']}"))
    if settings.confluence_space_key:
        results.append(_check(f"Confluence space {settings.confluence_space_key}", settings,
                              f"/wiki/api/v2/spaces?keys={settings.confluence_space_key}",
                              lambda j: (j["results"][0]["name"] if j.get("results")
                                         else "NOT FOUND (no access or wrong key)")))
    return all(results)
