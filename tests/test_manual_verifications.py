from collections.abc import Generator
from unittest.mock import patch

import pytest
import requests as req

from flatpak_builder_lint import domainutils


@pytest.fixture(autouse=True)
def mock_domainutils() -> None:
    pass


@pytest.fixture(autouse=True)
def clear_manual_verification_domains_cache() -> Generator[None, None, None]:
    domainutils._get_manual_verification_domains.cache_clear()
    yield
    domainutils._get_manual_verification_domains.cache_clear()


def test_get_manual_verification_domains() -> None:
    with patch("requests.get") as mock_get:
        response = mock_get.return_value
        response.status_code = 200
        response.headers = {"Content-Type": "text/plain"}
        response.request.headers = {}
        response.json.return_value = {
            "mx.unam.fciencias.aztlan.GTrophies": "AZTLAN.FCIENCIAS.UNAM.MX",
            "": "example.com",
            "org.example.Empty": "",
            "org.example.InvalidDomain": None,
        }

        result = domainutils._get_manual_verification_domains()

    assert result == {
        "mx.unam.fciencias.aztlan.GTrophies": "aztlan.fciencias.unam.mx"
    }
    mock_get.assert_called_once_with(
        "https://raw.githubusercontent.com/flathub-infra/website/HEAD/"
        "backend/app/staticfiles/manual_verifications.json",
        allow_redirects=False,
        timeout=domainutils.REQUEST_TIMEOUT,
    )


def test_get_manual_verification_domains_request_failure_returns_empty() -> None:
    with patch("requests.get", side_effect=req.exceptions.RequestException):
        result = domainutils._get_manual_verification_domains()

    assert result == {}


def test_get_manual_verification_domains_malformed_json_returns_empty() -> None:
    with patch("requests.get") as mock_get:
        response = mock_get.return_value
        response.status_code = 200
        response.headers = {"Content-Type": "text/plain"}
        response.request.headers = {}
        response.json.side_effect = req.exceptions.JSONDecodeError("Invalid JSON", "", 0)

        result = domainutils._get_manual_verification_domains()

    assert result == {}


def test_get_manual_verification_domains_non_object_returns_empty() -> None:
    with patch("requests.get") as mock_get:
        response = mock_get.return_value
        response.status_code = 200
        response.headers = {"Content-Type": "text/plain"}
        response.request.headers = {}
        response.json.return_value = ["aztlan.fciencias.unam.mx"]

        result = domainutils._get_manual_verification_domains()

    assert result == {}


def test_get_manual_verification_domains_non_200_returns_empty() -> None:
    with patch("requests.get") as mock_get:
        response = mock_get.return_value
        response.status_code = 404
        response.headers = {"Content-Type": "text/plain"}
        response.request.headers = {}

        result = domainutils._get_manual_verification_domains()

    assert result == {}
    response.json.assert_not_called()
