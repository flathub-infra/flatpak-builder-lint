from collections.abc import Generator

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
