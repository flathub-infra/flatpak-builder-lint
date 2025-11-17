import logging
import os

import requests

from . import config

logger = logging.getLogger(__name__)

ISSUE_TITLE = "Stale exceptions"
ISSUE_LABEL = "stale-exceptions"


def get_stale_exceptions(active_errors: set[str], exceptions: set[str]) -> set[str]:
    stale: set[str] = set()

    for exception in exceptions:
        if exception == "*":
            continue

        if exception.startswith(
            (
                "flathub-json-",
                "module-",
                "appid-unprefixed-bundled-extension-",
                "external-gitmodule-url-found",
                "manifest-",
                "toplevel-",
            )
        ):
            continue

        if exception not in active_errors:
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
            params={"state": "open", "creator": "flathubbot", "labels": ISSUE_LABEL},
            timeout=30,
        )
        response.raise_for_status()
        issues = response.json()

        existing_issue = next((i for i in issues if i["title"] == ISSUE_TITLE), None)
        exception_list = "\n".join(f"- {exc}" for exc in sorted(stale_exceptions))
        issue_body = f"Stale exceptions for `{appid}`:\n\n{exception_list}"

        if existing_issue:
            issue_number = existing_issue["number"]

            comments_url = (
                f"{config.GITHUB_API}/repos/"
                f"{config.LINTER_FULL_REPO}/issues/"
                f"{issue_number}/comments"
            )

            comments_resp = requests.get(comments_url, headers=headers, timeout=30)
            comments_resp.raise_for_status()
            comments = comments_resp.json()

            if any(comment["body"] == issue_body for comment in comments):
                return True

            post_resp = requests.post(
                comments_url, headers=headers, json={"body": issue_body}, timeout=30
            )
            post_resp.raise_for_status()
            return True

        create_url = f"{config.GITHUB_API}/repos/{config.LINTER_FULL_REPO}/issues"
        create_resp = requests.post(
            create_url,
            headers=headers,
            json={"title": ISSUE_TITLE, "body": issue_body, "labels": [ISSUE_LABEL]},
            timeout=30,
        )
        create_resp.raise_for_status()
        return True

    except requests.exceptions.RequestException as e:
        logger.debug(
            "Request exception when reporting stale exceptions for %s: %s: %s",
            appid,
            type(e).__name__,
            e,
        )
        return False
