import logging
import os

import requests

from . import config, domainutils

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
        logger.debug("No GITHUB_TOKEN found, cannot report stale exceptions")
        return False

    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        url_issues = f"{config.GITHUB_API}/repos/{config.LINTER_FULL_REPO}/issues"
        response = requests.get(
            url_issues,
            headers=headers,
            params={"state": "open", "creator": "flathubbot", "labels": ISSUE_LABEL},
            timeout=30,
        )
        logger.debug(
            "Request headers for %s: %s",
            url_issues,
            domainutils.filter_request_headers(dict(response.request.headers)),
        )
        logger.debug("Response headers for %s: %s", url_issues, dict(response.headers))
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
            logger.debug(
                "Request headers for %s: %s",
                comments_url,
                domainutils.filter_request_headers(dict(comments_resp.request.headers)),
            )
            logger.debug("Response headers for %s: %s", comments_url, dict(comments_resp.headers))
            comments_resp.raise_for_status()
            comments = comments_resp.json()

            if any(comment["body"] == issue_body for comment in comments):
                logger.debug("Comment already exists for %s, skipping", appid)
                return True

            post_resp = requests.post(
                comments_url, headers=headers, json={"body": issue_body}, timeout=30
            )
            logger.debug(
                "Request headers for %s: %s",
                comments_url,
                domainutils.filter_request_headers(dict(post_resp.request.headers)),
            )
            logger.debug("Response headers for %s: %s", comments_url, dict(post_resp.headers))
            post_resp.raise_for_status()
            return True

        create_url = f"{config.GITHUB_API}/repos/{config.LINTER_FULL_REPO}/issues"
        create_resp = requests.post(
            create_url,
            headers=headers,
            json={"title": ISSUE_TITLE, "body": issue_body, "labels": [ISSUE_LABEL]},
            timeout=30,
        )
        logger.debug(
            "Request headers for %s: %s",
            create_url,
            domainutils.filter_request_headers(dict(create_resp.request.headers)),
        )
        logger.debug("Response headers for %s: %s", create_url, dict(create_resp.headers))
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
