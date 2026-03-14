import json
import os
import tempfile
from unittest.mock import patch

import pytest
import requests as req

from flatpak_builder_lint import checks, cli, domainutils

EXCEPTIONS_DATA = {
    "org.flathub.test.App": {
        "*": {
            "finish-args-host-filesystem-access": "Applies to all repos",
        },
        "stable": {
            "finish-args-flatpak-spawn-access": "Only stable",
        },
        "beta": {
            "finish-args-arbitrary-dbus-access": "Only beta",
        },
    }
}


@pytest.fixture(autouse=True)
def reset_checks() -> None:
    checks.Check.errors = set()
    checks.Check.warnings = set()


def get_local_exceptions_side_effect(appid: str, exceptions_repo: str | None) -> set[str]:
    raw = EXCEPTIONS_DATA.get(appid, {})
    if not raw:
        return set()
    if exceptions_repo:
        return set(raw.get(exceptions_repo, {}).keys()) | set(raw.get("*", {}).keys())
    return {k for v in raw.values() for k in v}


@pytest.mark.parametrize(
    "repo, expected_present, expected_absent",
    [
        (
            None,
            {
                "finish-args-host-filesystem-access",
                "finish-args-flatpak-spawn-access",
                "finish-args-arbitrary-dbus-access",
            },
            set(),
        ),
        (
            "*",
            {"finish-args-host-filesystem-access"},
            {"finish-args-flatpak-spawn-access", "finish-args-arbitrary-dbus-access"},
        ),
        (
            "stable",
            {"finish-args-host-filesystem-access", "finish-args-flatpak-spawn-access"},
            {"finish-args-arbitrary-dbus-access"},
        ),
        (
            "beta",
            {"finish-args-host-filesystem-access", "finish-args-arbitrary-dbus-access"},
            {"finish-args-flatpak-spawn-access"},
        ),
        (
            "unknown",
            {"finish-args-host-filesystem-access"},
            {"finish-args-flatpak-spawn-access", "finish-args-arbitrary-dbus-access"},
        ),
    ],
)
def test_local_exceptions(
    repo: str | None, expected_present: set[str], expected_absent: set[str]
) -> None:
    with patch(
        "flatpak_builder_lint.cli.get_local_exceptions",
        side_effect=get_local_exceptions_side_effect,
    ):
        result = cli.get_local_exceptions("org.flathub.test.App", repo)

    for e in expected_present:
        assert e in result
    for e in expected_absent:
        assert e not in result


def test_local_exceptions_unknown_appid_returns_empty() -> None:
    with patch(
        "flatpak_builder_lint.cli.get_local_exceptions",
        side_effect=get_local_exceptions_side_effect,
    ):
        result = cli.get_local_exceptions("org.flathub.nonexistent.App", "stable")

    assert result == set()


@pytest.mark.parametrize(
    "repo, expected_present, expected_absent",
    [
        (
            None,
            {
                "finish-args-host-filesystem-access",
                "finish-args-flatpak-spawn-access",
                "finish-args-arbitrary-dbus-access",
            },
            set(),
        ),
        (
            "stable",
            {"finish-args-host-filesystem-access", "finish-args-flatpak-spawn-access"},
            {"finish-args-arbitrary-dbus-access"},
        ),
        (
            "beta",
            {"finish-args-host-filesystem-access", "finish-args-arbitrary-dbus-access"},
            {"finish-args-flatpak-spawn-access"},
        ),
    ],
)
def test_remote_exceptions_github(
    repo: str | None, expected_present: set[str], expected_absent: set[str]
) -> None:
    mock_data = {"org.flathub.test.App": EXCEPTIONS_DATA["org.flathub.test.App"]}

    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.headers = {"Content-Type": "text/plain"}
        mock_get.return_value.json.return_value = mock_data

        domainutils.get_remote_exceptions_github.cache_clear()
        result = domainutils.get_remote_exceptions_github("org.flathub.test.App", repo)

    for e in expected_present:
        assert e in result
    for e in expected_absent:
        assert e not in result


def test_remote_exceptions_github_request_failure_returns_empty() -> None:
    with patch("requests.get", side_effect=req.exceptions.RequestException):
        domainutils.get_remote_exceptions_github.cache_clear()
        result = domainutils.get_remote_exceptions_github("org.flathub.test.App", "stable")

    assert result == set()


def test_user_exceptions_ignores_repo() -> None:
    data = {"org.flathub.test.App": ["finish-args-host-filesystem-access"]}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        fname = f.name

    try:
        result = cli.get_user_exceptions(fname, "org.flathub.test.App")
        assert "finish-args-host-filesystem-access" in result
    finally:
        os.unlink(fname)
