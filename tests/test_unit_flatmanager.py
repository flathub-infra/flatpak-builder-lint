import gzip
import json
from pathlib import Path
from typing import Any

import pytest
from pytest import MonkeyPatch

from flatpak_builder_lint import checks
from flatpak_builder_lint.checks import flatmanager

BUILD_ID_ENV = "FLAT_MANAGER_BUILD_ID"
BUILD_INFO_ENV = "FLAT_MANAGER_BUILD_INFO"

APP_REF = "app/org.example.App/x86_64/test"

VALID_INFO: dict[str, Any] = {
    "build": {"repo": "test", "token_type": "app"},
    "build_refs": [{"ref_name": APP_REF}],
}


def _set_build_info(monkeypatch: MonkeyPatch, info: Any) -> None:
    monkeypatch.setenv(BUILD_ID_ENV, "66707")
    monkeypatch.setenv(BUILD_INFO_ENV, json.dumps(info))


def _run_check(monkeypatch: MonkeyPatch, path: Path, info: Any) -> set[str]:
    _set_build_info(monkeypatch, info)
    flatmanager.FlatManagerCheck().check_repo(str(path))
    return checks.Check.errors


def _write_appstream(path: Path, xml: str) -> None:
    appstream_path = path / "appstream" / "x86_64" / "appstream.xml.gz"
    appstream_path.parent.mkdir(parents=True)
    with gzip.open(appstream_path, "wt") as f:
        f.write(xml)


def test_get_build_extended_reads_projected_metadata(monkeypatch: MonkeyPatch) -> None:
    _set_build_info(monkeypatch, VALID_INFO)
    assert flatmanager.get_build_extended() == VALID_INFO


def test_get_build_extended_returns_none_without_build_id(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv(BUILD_ID_ENV, raising=False)
    monkeypatch.delenv(BUILD_INFO_ENV, raising=False)
    assert flatmanager.get_build_extended() is None
    assert flatmanager.is_direct_upload_build() is False


def test_get_build_extended_fails_without_info_in_pipeline(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv(BUILD_ID_ENV, "66707")
    monkeypatch.delenv(BUILD_INFO_ENV, raising=False)
    with pytest.raises(RuntimeError, match=BUILD_INFO_ENV):
        flatmanager.get_build_extended()


@pytest.mark.parametrize(
    "raw",
    [
        "{",
        "[]",
        "null",
        '"build"',
        "{}",
        '{"build_refs": []}',
        '{"build": [], "build_refs": []}',
        '{"build": {}, "build_refs": []}',
        '{"build": {"repo": 1}, "build_refs": []}',
        '{"build": {"repo": "stable"}}',
        '{"build": {"repo": "stable"}, "build_refs": {}}',
        '{"build": {"repo": "stable"}, "build_refs": ["app/org.example.App/x86_64/stable"]}',
        '{"build": {"repo": "stable"}, "build_refs": [{}]}',
        '{"build": {"repo": "stable"}, "build_refs": [{"ref_name": 1}]}',
    ],
)
def test_get_build_extended_rejects_malformed_info(monkeypatch: MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv(BUILD_ID_ENV, "66707")
    monkeypatch.setenv(BUILD_INFO_ENV, raw)
    with pytest.raises(RuntimeError):
        flatmanager.get_build_extended()
    assert flatmanager.is_direct_upload_build() is False


def test_is_direct_upload_build_true(monkeypatch: MonkeyPatch) -> None:
    _set_build_info(monkeypatch, {"build": {"repo": "test", "token_type": "app"}, "build_refs": []})
    assert flatmanager.is_direct_upload_build() is True


@pytest.mark.parametrize(
    "build",
    [
        {"repo": "test", "token_type": "user"},
        {"repo": "test", "token_type": ""},
        {"repo": "test", "token_type": None},
        {"repo": "test"},
    ],
)
def test_is_direct_upload_build_false_for_other_token_types(
    monkeypatch: MonkeyPatch, build: dict[str, Any]
) -> None:
    _set_build_info(monkeypatch, {"build": build, "build_refs": []})
    assert flatmanager.is_direct_upload_build() is False


def test_check_fails_without_metadata_in_pipeline(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(BUILD_ID_ENV, "66707")
    monkeypatch.delenv(BUILD_INFO_ENV, raising=False)
    with pytest.raises(RuntimeError, match=BUILD_INFO_ENV):
        flatmanager.FlatManagerCheck().check_repo(str(tmp_path))


@pytest.mark.parametrize(
    ("repo", "ref", "expected_errors"),
    [
        (
            "stable",
            "app/org.example.App/x86_64/beta",
            {"flat-manager-wrong-ref-branch-for-stable-repo", "flat-manager-branch-repo-mismatch"},
        ),
        (
            "beta",
            "app/org.example.App/x86_64/stable",
            {"flat-manager-wrong-ref-branch-for-beta-repo", "flat-manager-branch-repo-mismatch"},
        ),
        ("test", "app/org.example.App/x86_64/stable", set()),
        ("test", "app/org.example.App/x86_64/nightly", {"flat-manager-branch-repo-mismatch"}),
    ],
)
def test_branch_policy_enforced_from_projected_metadata(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    repo: str,
    ref: str,
    expected_errors: set[str],
) -> None:
    info = {"build": {"repo": repo, "token_type": "user"}, "build_refs": [{"ref_name": ref}]}
    assert _run_check(monkeypatch, tmp_path, info) == expected_errors


def test_app_token_without_app_ref_is_rejected(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    info = {
        "build": {"repo": "stable", "token_type": "app"},
        "build_refs": [{"ref_name": "runtime/org.example.App.Locale/x86_64/stable"}],
    }
    assert _run_check(monkeypatch, tmp_path, info) == {"flat-manager-no-app-ref-uploaded"}


def test_app_token_manifest_key_absent_is_rejected(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    _write_appstream(
        tmp_path, '<component type="desktop-application"><id>org.example.App</id></component>'
    )
    info = {
        "build": {"repo": "stable", "token_type": "app"},
        "build_refs": [{"ref_name": "app/org.example.App/x86_64/stable"}],
    }
    assert _run_check(monkeypatch, tmp_path, info) == {"appstream-no-flathub-manifest-key"}


def test_app_token_manifest_key_present_is_allowed(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    _write_appstream(
        tmp_path,
        '<component type="desktop-application"><id>org.example.App</id>'
        '<custom><value key="flathub::manifest">'
        "https://github.com/flathub/org.example.App/blob/master/org.example.App.json"
        "</value></custom></component>",
    )
    info = {
        "build": {"repo": "stable", "token_type": "app"},
        "build_refs": [{"ref_name": "app/org.example.App/x86_64/stable"}],
    }
    assert _run_check(monkeypatch, tmp_path, info) == set()
