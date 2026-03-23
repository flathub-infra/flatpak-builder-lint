import os
import shutil
import tempfile
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from flatpak_builder_lint import checks


@pytest.fixture(autouse=True)
def reset_check_state() -> Generator[None, None, None]:
    original_all = checks.ALL[:]
    checks.Check.errors = set()
    checks.Check.warnings = set()
    checks.Check.jsonschema = set()
    checks.Check.appstream = set()
    checks.Check.desktopfile = set()
    checks.Check.info = set()
    checks.Check.repo_primary_refs = set()
    yield
    checks.ALL.clear()
    checks.ALL.extend(original_all)
    checks.Check.errors = set()
    checks.Check.warnings = set()
    checks.Check.jsonschema = set()
    checks.Check.appstream = set()
    checks.Check.desktopfile = set()
    checks.Check.info = set()
    checks.Check.repo_primary_refs = set()


@pytest.fixture(scope="module")
def tests_subdir() -> str:
    return "builddir"


@pytest.fixture(scope="module")
def eol_runtimes() -> set[str]:
    return {"org.freedesktop.Platform//18.08", "org.gnome.Sdk//40"}


@pytest.fixture(scope="module")
def tmp_testdir(tests_subdir: str) -> Generator[str, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        targetdir = os.path.join(tmpdir, "tests", tests_subdir)
        shutil.copytree(f"tests/{tests_subdir}", targetdir, symlinks=True)
        yield tmpdir


@pytest.fixture(autouse=True)
def change_to_tmpdir(
    request: pytest.FixtureRequest, tmp_testdir: str
) -> Generator[None, None, None]:
    if request.node.get_closest_marker("integration"):
        yield
        return
    original_dir = os.getcwd()
    os.chdir(tmp_testdir)
    yield
    os.chdir(original_dir)


@pytest.fixture(autouse=True)
def mock_domainutils(
    request: pytest.FixtureRequest, eol_runtimes: set[str]
) -> Generator[dict[str, MagicMock], None, None]:
    if request.node.get_closest_marker("integration"):
        yield {}
        return
    with (
        patch("flatpak_builder_lint.domainutils.check_url") as mock_check_url,
        patch("flatpak_builder_lint.domainutils.is_app_on_flathub_summary") as mock_is_on_flathub,
        patch("flatpak_builder_lint.domainutils.get_eol_runtimes_on_flathub") as mock_get_eol,
        patch(
            "flatpak_builder_lint.domainutils.get_remote_exceptions_github"
        ) as mock_exceptions_gh,
        patch(
            "flatpak_builder_lint.domainutils.get_remote_exceptions_flathub"
        ) as mock_exceptions_fh,
    ):
        mock_check_url.return_value = (True, None)
        mock_is_on_flathub.return_value = False
        mock_get_eol.return_value = eol_runtimes
        mock_exceptions_gh.return_value = set()
        mock_exceptions_fh.return_value = set()

        yield {
            "check_url": mock_check_url,
            "is_app_on_flathub_summary": mock_is_on_flathub,
            "get_eol_runtimes_on_flathub": mock_get_eol,
            "get_remote_exceptions_github": mock_exceptions_gh,
            "get_remote_exceptions_flathub": mock_exceptions_fh,
        }


@pytest.fixture(params=["builddir", "repo"])
def check_type(request: pytest.FixtureRequest) -> str:
    return str(request.param)
