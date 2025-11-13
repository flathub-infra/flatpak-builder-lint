import os

import requests

from . import config

ISSUE_TITLE = "Stale exceptions"
ISSUE_LABEL = "stale-exceptions"


def get_stale_exceptions(active_errors: set[str], exceptions: set[str]) -> set[str]:
    stale: set[str] = set()

    for exception in exceptions:
        if exception == "*":
            continue

        is_used = False
        for issue in active_errors:
            if issue == exception:
                is_used = True
                break

        if not is_used:
            stale.add(exception)

    return stale


def report_stale_exceptions(appid: str, stale_exceptions: set[str]) -> bool:
    if not stale_exceptions:
        return True

    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        return False

    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        response = requests.get(
            f"{config.GITHUB_API}/repos/{config.LINTER_FULL_REPO}/issues",
            headers=headers,
            params={
                "state": "open",
                "creator": "flathubbot",
                "labels": ISSUE_LABEL,
            },
            timeout=30,
        )
        response.raise_for_status()
        issues = response.json()

        existing_issue = next((i for i in issues if i["title"] == ISSUE_TITLE), None)
        exception_list = "\n".join(f"- {exc}" for exc in sorted(stale_exceptions))

        if existing_issue:
            issue_number = existing_issue["number"]

            comments_resp = requests.get(
                f"{config.GITHUB_API}/repos/{config.LINTER_FULL_REPO}/issues/{issue_number}/comments",
                headers=headers,
                timeout=30,
            )
            comments_resp.raise_for_status()
            comments = comments_resp.json()

            if any(f"`{appid}`" in comment["body"] for comment in comments):
                return True

            comment_body = f"""Stale exceptions for `{appid}`:

{exception_list}"""

            post_resp = requests.post(
                f"{config.GITHUB_API}/repos/{config.LINTER_FULL_REPO}/issues/{issue_number}/comments",
                headers=headers,
                json={"body": comment_body},
                timeout=30,
            )
            post_resp.raise_for_status()
            return True

        issue_body = f"""Stale exceptions for `{appid}`:

{exception_list}"""

        create_resp = requests.post(
            f"{config.GITHUB_API}/repos/{config.LINTER_FULL_REPO}/issues",
            headers=headers,
            json={
                "title": ISSUE_TITLE,
                "body": issue_body,
                "labels": [ISSUE_LABEL],
            },
            timeout=30,
        )
        create_resp.raise_for_status()
        return True

    except requests.exceptions.RequestException:
        return False
