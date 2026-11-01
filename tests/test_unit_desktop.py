import gzip
import json
import os
from pathlib import Path

import pytest

from flatpak_builder_lint.checks.desktop import DesktopfileCheck
from flatpak_builder_lint.cli import print_gh_annotations
from tests.testlib import commit_to_repo

APPID = "org.example.Symlink"
SECRET = "SYNTHETIC_DESKTOP_SECRET_63829"


@pytest.fixture
def desktop_build(tmp_path: Path) -> Path:
    build = tmp_path / "build"
    applications = build / "files/share/applications"
    applications.mkdir(parents=True)
    (build / "metadata").write_text(
        f"[Application]\nname={APPID}\nruntime=org.freedesktop.Platform/x86_64/26.08\n"
    )
    (applications / f"{APPID}.desktop").write_text(
        f"[Desktop Entry]\nType=Application\nName=Example\nExec=example\n"
        f"Icon={APPID}\nCategories=Utility;\n"
    )
    catalogue = build / f"files/share/app-info/xmls/{APPID}.xml.gz"
    catalogue.parent.mkdir(parents=True)
    with gzip.open(catalogue, "wt") as stream:
        stream.write(
            f'<components><component type="desktop-application"><id>{APPID}</id>'
            "</component></components>"
        )
    return build


def check_desktop(build: Path, check_type: str, tmp_path: Path) -> DesktopfileCheck:
    check = DesktopfileCheck()
    if check_type == "builddir":
        check.check_build(str(build))
    else:
        repo = tmp_path / f"repo-{check_type}"
        commit_to_repo(str(build), str(repo))
        check.check_repo(str(repo))
    return check


@pytest.mark.parametrize("attack", ["primary", "secondary"])
@pytest.mark.parametrize("check_type", ["builddir", "repo"])
def test_outside_desktop_content_stays_private(
    desktop_build: Path,
    tmp_path: Path,
    check_type: str,
    attack: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret = tmp_path / "secret.json"
    secret.write_text(json.dumps({"token": SECRET}))
    applications = desktop_build / "files/share/applications"
    name = f"{APPID}.desktop" if attack == "primary" else f"{APPID}-leak.desktop"
    desktop = applications / name
    desktop.unlink(missing_ok=True)
    desktop.symlink_to(secret)

    check = check_desktop(desktop_build, check_type, tmp_path)

    assert "desktop-file-unsafe-path" in check.errors
    results: dict[str, str | list[str]] = {
        "errors": sorted(check.errors),
        "desktopfile": sorted(check.desktopfile),
    }
    assert SECRET not in json.dumps(results)
    print_gh_annotations(results, check_type)
    assert SECRET not in capsys.readouterr().out


def test_outside_applications_directory_is_rejected(desktop_build: Path, tmp_path: Path) -> None:
    secret = tmp_path / "secret.json"
    secret.write_text(json.dumps({"token": SECRET}))
    applications = desktop_build / "files/share/applications"
    outside = tmp_path / "outside-applications"
    outside.mkdir()
    (outside / f"{APPID}.desktop").write_text(secret.read_text())
    for entry in applications.iterdir():
        entry.unlink()
    applications.rmdir()
    applications.symlink_to(outside, target_is_directory=True)

    check = check_desktop(desktop_build, "builddir", tmp_path)

    assert "desktop-file-unsafe-path" in check.errors
    assert SECRET not in json.dumps(sorted(check.desktopfile))


def test_in_artifact_desktop_symlink_is_validated(
    desktop_build: Path, tmp_path: Path, check_type: str
) -> None:
    applications = desktop_build / "files/share/applications"
    desktop = applications / f"{APPID}.desktop"
    target = applications / "target"
    desktop.rename(target)
    target.write_text(target.read_text() + "Hidden=true\n")
    desktop.symlink_to(target.name)

    check = check_desktop(desktop_build, check_type, tmp_path)

    assert "desktop-file-is-hidden" in check.errors
    assert "desktop-file-unsafe-path" not in check.errors


def test_desktop_symlink_swap_cannot_escape(
    desktop_build: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = tmp_path / "secret.json"
    secret.write_text(json.dumps({"token": SECRET}))
    desktop = desktop_build / f"files/share/applications/{APPID}.desktop"
    original_open = os.open

    def swap_before_open(
        path: str | Path, flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        if path == desktop.name:
            desktop.unlink(missing_ok=True)
            desktop.symlink_to(secret)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", swap_before_open)
    check = DesktopfileCheck()
    check.check_build(str(desktop_build))

    assert "desktop-file-unsafe-path" in check.errors
    assert SECRET not in json.dumps(sorted(check.desktopfile))


def test_malformed_primary_desktop_reports_validation_failure(
    desktop_build: Path, tmp_path: Path, check_type: str
) -> None:
    (desktop_build / f"files/share/applications/{APPID}.desktop").write_text("{\n")

    check = check_desktop(desktop_build, check_type, tmp_path)

    assert "desktop-file-failed-validation" in check.errors
