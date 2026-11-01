from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

from flatpak_builder_lint.checks import flatmanager


def _build_extended(token_type: Any) -> dict[str, Any]:
    return {"build": {"token_type": token_type}, "build_refs": []}


@pytest.mark.parametrize("build_extended", [_build_extended("app")])
def test_is_direct_upload_build_true(build_extended: dict[str, Any]) -> None:
    with patch.object(flatmanager, "get_build_extended", return_value=build_extended):
        assert flatmanager.is_direct_upload_build() is True


@pytest.mark.parametrize(
    "build_extended",
    [
        _build_extended(""),
        _build_extended(None),
        {"build": {}, "build_refs": []},
        {"build": None, "build_refs": []},
        {"build": [], "build_refs": []},
        {"build_refs": []},
        None,
        [],
        "build",
    ],
)
def test_is_direct_upload_build_false(build_extended: Any) -> None:
    with patch.object(flatmanager, "get_build_extended", return_value=build_extended):
        assert flatmanager.is_direct_upload_build() is False


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("No flat-manager URL configured"),
        RuntimeError("Failed to fetch build info from flat-manager: 502"),
        requests.RequestException("connection reset"),
        OSError("Cannot read /etc/flathub-hooks.json"),
        ValueError("Bad response"),
        TypeError("Bad response"),
    ],
)
def test_is_direct_upload_build_fails_closed_on_lookup_error(error: Exception) -> None:
    with patch.object(flatmanager, "get_build_extended", side_effect=error):
        assert flatmanager.is_direct_upload_build() is False


def test_is_direct_upload_build_false_without_build_id() -> None:
    with patch.dict("os.environ", {}, clear=True):
        assert flatmanager.get_build_extended() is None
        assert flatmanager.is_direct_upload_build() is False


def test_build_cache_keyed_by_build_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLAT_MANAGER_URL", "https://hub.example.test")
    monkeypatch.setenv("FLAT_MANAGER_TOKEN", "token")

    response = MagicMock(status_code=200, headers={}, request=MagicMock(headers={}))
    response.json.side_effect = [
        _build_extended("app"),
        _build_extended(""),
    ]

    with patch("flatpak_builder_lint.checks.flatmanager.requests.get", return_value=response):
        monkeypatch.setenv("FLAT_MANAGER_BUILD_ID", "1")
        assert flatmanager.is_direct_upload_build() is True

        monkeypatch.setenv("FLAT_MANAGER_BUILD_ID", "2")
        assert flatmanager.is_direct_upload_build() is False

    assert response.json.call_count == 2
