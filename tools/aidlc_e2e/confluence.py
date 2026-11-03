"""Publish repo markdown pages to the Confluence design space (create only, never overwrites).

`uv run aidlc-e2e publish` uses the REST API with JIRA_EMAIL + JIRA_API_TOKEN from the env file.
The token is never printed.
"""

from __future__ import annotations

import html as htmllib
import posixpath
import re
import subprocess
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
    ("AIDLC · Requirement traceability", PROJECT_ROOT / "aidlc-docs" / "traceability.md"),
    ("AIDLC · High-level design (DRAFT)", PROJECT_ROOT / "aidlc-docs" / "design" / "hld.md"),
]


def _code_macros(html: str) -> str:
    """Turn <pre><code> blocks into Confluence code macros (Mermaid diagrams show as source)."""
    def repl(m: re.Match) -> str:
        lang = m.group(1) or "none"
        lang = "none" if lang == "mermaid" else lang
        code = htmllib.unescape(m.group(2)).replace("]]>", "]]]]><![CDATA[>")
        return (f'<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">{lang}</ac:parameter>'
                f"<ac:plain-text-body><![CDATA[{code}]]></ac:plain-text-body></ac:structured-macro>")
    return re.sub(r'<pre><code(?: class="language-([\w-]+)")?>(.*?)</code></pre>', repl, html, flags=re.S)


def _repo_web_url() -> str:
    """https://github.com/<owner>/<repo>/blob/main, from the origin remote; empty if unknown."""
    try:
        url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=PROJECT_ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""
    return re.sub(r"\.git$", "", url) + "/blob/main" if url.startswith("https://github.com/") else ""


def _link_repo_paths(text: str, path) -> str:
    """Repo-relative links become GitHub links when the remote is known, else plain text."""
    base = _repo_web_url()
    rel_dir = posixpath.dirname(str(path.relative_to(PROJECT_ROOT)))

    def repl(m: re.Match) -> str:
        label, target = m.group(1), m.group(2)
        if not base or target.startswith("#"):
            return label
        file_part, _, frag = target.partition("#")
        full = posixpath.normpath(posixpath.join(rel_dir, file_part))
        return f"[{label}]({base}/{full}{'#' + frag if frag else ''})"
    return re.sub(r"\[([^\]]+)\]\((?!https?:)([^)]*)\)", repl, text)


def to_storage(path) -> str:
    text = re.sub(r"\A---\n.*?\n---\n", "", path.read_text(), flags=re.S)
    text = re.sub(r"^# .*\n", "", text, count=1, flags=re.M)  # page title carries the H1
    text = _link_repo_paths(text, path)
    html = _code_macros(markdown.markdown(text, extensions=["tables", "fenced_code"]))
    return html + f"<p><em>Source: {path.relative_to(PROJECT_ROOT)} in the repo. Edit there. Diagrams are Mermaid source; render them from the repo.</em></p>"


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
