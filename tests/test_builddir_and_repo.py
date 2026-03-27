import os
from typing import Any
from unittest.mock import MagicMock

from pytest import MonkeyPatch

from tests.testlib import (
    create_app_icon,
    create_catalogue,
    create_catalogue_icon,
    create_elf,
    create_file,
    move_files,
    run_checks,
)


def rc(
    path: str,
    check_type: str,
    tmp_testdir: str,
) -> dict[str, Any]:
    return run_checks(path, check_type, tmp_root=tmp_testdir)


def test_appid(check_type: str, tmp_testdir: str) -> None:
    errors = {"appid-ends-with-lowercase-desktop", "appid-uses-code-hosting-domain"}
    ret = rc("tests/builddir/appid", check_type, tmp_testdir)
    found_errors = set(ret["errors"])
    assert errors.issubset(found_errors)
    assert "appstream-metainfo-missing" in found_errors


def test_url_not_reachable(
    check_type: str, tmp_testdir: str, mock_domainutils: dict[str, MagicMock]
) -> None:
    mock_domainutils["check_url"].return_value = (False, "Status: 404 | Body: Not Found")
    mock_domainutils["is_app_on_flathub_summary"].return_value = False

    ret = rc("tests/builddir/wrong-rdns-appid", check_type, tmp_testdir)
    assert "appid-url-not-reachable" in set(ret["errors"])


def test_finish_args(check_type: str, tmp_testdir: str) -> None:
    errors = {
        "finish-args-arbitrary-dbus-access",
        "finish-args-flatpak-spawn-access",
        "finish-args-incorrect-dbus-gvfs",
        "finish-args-wildcard-freedesktop-talk-name",
        "finish-args-portal-talk-name",
        "finish-args-absolute-run-media-path",
        "finish-args-has-nodevice-dri",
        "finish-args-has-unshare-network",
        "finish-args-has-nosocket-cups",
        "finish-args-freedesktop-dbus-talk-name",
        "finish-args-freedesktop-dbus-system-talk-name",
        "finish-args-x11-without-ipc",
        "finish-args-flatpak-user-folder-access",
        "finish-args-host-tmp-access",
        "finish-args-flatpak-appdata-folder-access",
        "finish-args-host-var-access",
        "finish-args-legacy-icon-folder-permission",
        "finish-args-legacy-font-folder-permission",
        "finish-args-incorrect-theme-folder-permission",
        "finish-args-autostart-filesystem-access",
        "finish-args-desktopfile-filesystem-access",
        "finish-args-ssh-filesystem-access",
        "finish-args-gnupg-filesystem-access",
        "finish-args-uses-no-talk-name",
        "finish-args-has-socket-gpg-agent",
        "finish-args-has-socket-ssh-auth",
        "finish-args-plasmashell-talk-name",
        "finish-args-systemd1-talk-name",
        "finish-args-own-name-wildcard-org.gnome",
        "finish-args-own-name-org.freedesktop.login1",
        "finish-args-own-name-org.kde.KWin",
        "finish-args-own-name-wildcard-org.kde",
        "finish-args-system-own-name-wildcard-org.gnome",
        "finish-args-own-name-org.freedesktop.impl.portal.PermissionStore",
        "finish-args-own-name-org.kde.StatusNotifierItem",
        "finish-args-full-home-cache-access",
        "finish-args-full-home-local-access",
        "finish-args-host-root-filesystem-access",
        "finish-args-host-os-filesystem-access",
        "finish-args-host-etc-filesystem-access",
        "finish-args-contains-inherit-wayland-socket",
        "finish-args-unnecessary-appid-own-name",
        "finish-args-unnecessary-appid-mpris-own-name",
        "finish-args-mpris-flatpak-id-talk-name",
    }
    expected_absents = {
        "finish-args-has-nodevice-shm",
        "finish-args-has-nosocket-fallback-x11",
        "finish-args-own-name-org.flathub.finish_args",
        "finish-args-own-name-org.mpris.MediaPlayer2.org.flathub.finish_args",
        "finish-args-own-name-org.mpris.MediaPlayer2.foobar",
    }

    ret = rc("tests/builddir/finish_args", check_type, tmp_testdir)
    found_errors = set(ret["errors"])

    assert errors.issubset(found_errors)
    for a in expected_absents:
        assert a not in found_errors
    for err in found_errors:
        assert not err.startswith(("finish-args-arbitrary-xdg-", "finish-args-unnecessary-xdg-"))


def test_finish_args_new_metadata(check_type: str, tmp_testdir: str) -> None:
    ret = rc("tests/builddir/finish_args_new_metadata", check_type, tmp_testdir)
    assert "finish-args-no-required-flatpak" in set(ret["errors"])


def test_display_supported(check_type: str, tmp_testdir: str) -> None:
    absents = {"finish-args-fallback-x11-without-wayland", "finish-args-only-wayland"}
    ret = rc("tests/builddir/display-supported", check_type, tmp_testdir)
    found_errors = set(ret["errors"])
    for a in absents:
        assert a not in found_errors


def test_finish_args_missing(check_type: str, tmp_testdir: str) -> None:
    ret = rc("tests/builddir/finish_args_missing", check_type, tmp_testdir)
    assert "finish-args-not-defined" in set(ret["errors"])


def test_flathub_json(check_type: str, tmp_testdir: str) -> None:
    testdir = "tests/builddir/flathub_json"
    move_files(testdir)
    ret = rc(testdir, check_type, tmp_testdir)
    assert "flathub-json-skip-appstream-check" in set(ret["errors"])


def test_console(check_type: str, tmp_testdir: str) -> None:
    errors = {
        "finish-args-not-defined",
        "desktop-file-exec-key-absent",
        "desktop-file-is-hidden",
        "desktop-file-terminal-key-not-true",
    }
    testdir = "tests/builddir/console"
    move_files(testdir)
    create_catalogue(testdir, "org.flathub.example.console.xml")
    ret = rc(testdir, check_type, tmp_testdir)
    found_errors = set(ret["errors"])
    assert "appstream-unsupported-component-type" not in found_errors
    assert errors == found_errors


def test_appstream_unsupported_ctype(check_type: str, tmp_testdir: str) -> None:
    testdir = "tests/builddir/appstream-unsupported-ctype"
    move_files(testdir)
    create_catalogue(testdir, "org.flathub.appstream_unsupported_ctype.xml")
    ret = rc(testdir, check_type, tmp_testdir)
    assert "appstream-unsupported-component-type" in set(ret["errors"])


def test_metadata_spaces(check_type: str, tmp_testdir: str) -> None:
    rc("tests/builddir/metadata-spaces", check_type, tmp_testdir)


def test_desktop_file(check_type: str, tmp_testdir: str) -> None:
    testdir = "tests/builddir/desktop-file"
    move_files(testdir)
    icons = ["com.github.flathub_infra.desktop-file.Devel.png", "org.flathub.foo.png"]
    create_catalogue(testdir, "com.github.flathub_infra.desktop-file.xml")
    for i in icons:
        create_app_icon(testdir, i)
    ret = rc(testdir, check_type, tmp_testdir)
    errors = {
        "desktop-file-icon-key-wrong-value",
        "desktop-file-is-hidden",
        "desktop-file-exec-has-flatpak-run",
        "desktop-file-icon-not-installed",
        "desktop-file-low-quality-category",
    }
    found_errors = set(ret["errors"])
    for err in errors:
        assert err in found_errors
    assert "appstream-missing-categories" not in found_errors


def test_misplaced_icons(check_type: str, tmp_testdir: str) -> None:
    testdir = "tests/builddir/misplaced-icons"
    move_files(testdir)
    create_catalogue(testdir, "org.flathub.example.misplaced-icons.xml")
    create_catalogue_icon(testdir, "org.flathub.example.misplaced-icons.png")
    create_app_icon(
        testdir, "org.flathub.example.misplaced-icons.png", scalable=True, hicolor=False
    )
    create_app_icon(testdir, "org.flathub.example.misplaced-icons.svg")
    ret = rc(testdir, check_type, tmp_testdir)
    found_errors = set(ret["errors"])
    assert "non-png-icon-in-hicolor-size-folder" in found_errors
    assert "non-svg-icon-in-scalable-folder" in found_errors


def test_quality_guidelines(check_type: str, tmp_testdir: str) -> None:
    testdir = "tests/builddir/appdata-quality"
    move_files(testdir)
    create_catalogue(testdir, "com.github.flathub.appdata-quality.xml")
    create_app_icon(testdir, "foo")
    ret = rc(testdir, check_type, tmp_testdir)
    found_errors = set(ret["errors"])
    found_warnings = set(ret["warnings"])
    for e in (
        "appstream-missing-developer-name",
        "appstream-missing-project-license",
        "no-exportable-icon-installed",
        "appstream-launchable-file-missing",
    ):
        assert e in found_errors
    assert "appstream-screenshot-missing-caption" in found_warnings
    # If present, it means a metainfo file that was validating
    # correctly broke and that should be fixed
    for e in (
        "appstream-failed-validation",
        "appstream-id-mismatch-flatpak-id",
        "metainfo-missing-launchable-tag",
    ):
        assert e not in found_errors


def test_broken_icon(check_type: str, tmp_testdir: str) -> None:
    testdir = "tests/builddir/appstream-broken-icon"
    move_files(testdir)
    create_catalogue(testdir, "org.flathub.appstream_broken_icon.xml")
    create_file(os.path.join(testdir, "files/share/applications"), "org.foo.test.desktop")
    ret = rc(testdir, check_type, tmp_testdir)
    found_errors = set(ret["errors"])
    found_warnings = set(ret["warnings"])
    for e in (
        # Expected failure with appstreamcli validate
        "appstream-failed-validation",
        "no-exportable-icon-installed",
        "metainfo-launchable-tag-wrong-value",
        "finish-args-not-defined",
        "desktop-file-not-installed",
    ):
        assert e in found_errors
    assert "appid-url-check-internal-error" not in found_errors
    assert "appstream-missing-vcs-browser-url" in found_warnings


def test_broken_remote_icon(check_type: str, tmp_testdir: str) -> None:
    testdir = "tests/builddir/appstream-broken-remote-icon"
    move_files(testdir)
    create_catalogue(testdir, "org.flathub.appstream_broken_remote_icon.xml")
    create_catalogue_icon(testdir, "org.flathub.appstream_broken_remote_icon.png")
    ret = rc(testdir, check_type, tmp_testdir)
    found_errors = set(ret["errors"])
    assert "appstream-remote-icon-not-mirrored" in found_errors
    assert "appstream-missing-categories" in found_errors
    assert "metainfo-launchable-tag-wrong-value" not in found_errors


def test_appstream_no_icon_file(check_type: str, tmp_testdir: str) -> None:
    testdir = "tests/builddir/appstream-no-icon-file"
    move_files(testdir)
    create_catalogue(testdir, "org.flathub.appstream_no_icon_file.xml")
    ret = rc(testdir, check_type, tmp_testdir)
    assert "appstream-missing-icon-file" in set(ret["errors"])


def test_appstream_icon_key_no_type(check_type: str, tmp_testdir: str) -> None:
    testdir = "tests/builddir/appstream-icon-key-no-type"
    move_files(testdir)
    create_catalogue(testdir, "org.flathub.appstream_icon_key_no_type.xml")
    create_catalogue_icon(testdir, "org.flathub.appstream_icon_key_no_type.png")
    ret = rc(testdir, check_type, tmp_testdir)
    assert "appstream-icon-key-no-type" in set(ret["errors"])
    assert ret.get("warnings", []) == []


def test_min_success_metadata(check_type: str, tmp_testdir: str) -> None:
    # Illustrate the minimum metadata required to pass linter
    # These should not be broken
    for builddir in (
        "org.electronjs.Electron200.BaseApp",
        "org.gtk.Gtk33theme.Helium-dark",
        "org.flathub.gui",
    ):
        testdir = f"tests/builddir/min_success_metadata/{builddir}"

        if builddir == "org.flathub.gui":
            move_files(testdir)
            create_catalogue(testdir, "org.flathub.gui.xml")
            create_app_icon(testdir, "org.flathub.gui.png")
            create_catalogue_icon(testdir, "org.flathub.gui.png")
            create_file(os.path.join(testdir, "screenshots"), "org.flathub.gui-screenshot.png")

        ret = rc(testdir, check_type, tmp_testdir)
        assert "errors" not in ret

    cli_testdir = "tests/builddir/min_success_metadata/org.flathub.cli"
    move_files(cli_testdir)
    create_catalogue(cli_testdir, "org.flathub.cli.xml")
    ret = rc(cli_testdir, check_type, tmp_testdir)
    found_errors = set(ret["errors"])
    # CLI applications are allowed to have no finish-args with exceptions
    assert len(found_errors - {"finish-args-not-defined"}) == 0
    for n in (
        "appid-too-many-components-for-app",
        "metainfo-missing-launchable-tag",
        "appid-url-check-internal-error",
        "appid-url-not-reachable",
        "appstream-no-flathub-manifest-key",
        "appstream-flathub-manifest-url-not-reachable",
    ):
        assert n not in found_errors


def test_aps_cid_mismatch_flatpak_id(check_type: str, tmp_testdir: str) -> None:
    testdir = "tests/builddir/appstream-cid-mismatch-flatpak-id"
    move_files(testdir)
    create_catalogue(testdir, "org.flathub.appstream-cid-mismatch-flatpak-id.xml")
    ret = rc(testdir, check_type, tmp_testdir)
    assert "appstream-id-mismatch-flatpak-id" in set(ret["errors"])


def test_dconf_access(check_type: str, tmp_testdir: str) -> None:
    ret = rc("tests/builddir/dconf-access", check_type, tmp_testdir)
    found_errors = set(ret["errors"])
    assert "finish-args-dconf-talk-name" in found_errors
    assert "finish-args-direct-dconf-path" in found_errors


def test_xdg_dir_access(check_type: str, tmp_testdir: str) -> None:
    ret = rc("tests/builddir/finish_args_xdg_dirs", check_type, tmp_testdir)
    found_errors = set(ret["errors"])
    for e in (
        "finish-args-arbitrary-xdg-config-ro-access",
        "finish-args-arbitrary-xdg-cache-ro-access",
        "finish-args-arbitrary-xdg-data-ro-access",
        "finish-args-arbitrary-xdg-config-rw-access",
        "finish-args-arbitrary-xdg-cache-rw-access",
        "finish-args-arbitrary-xdg-data-rw-access",
        "finish-args-arbitrary-xdg-config-create-access",
        "finish-args-arbitrary-xdg-cache-create-access",
        "finish-args-arbitrary-xdg-data-create-access",
        "finish-args-unnecessary-xdg-cache-electron-create-access",
        "finish-args-unnecessary-xdg-config-fonts-rw-access",
        "finish-args-unnecessary-xdg-data-gvfs-ro-access",
    ):
        assert e in found_errors


def test_appstream_missing_timestamp(check_type: str, tmp_testdir: str) -> None:
    testdir = "tests/builddir/appstream-missing-timestamp"
    move_files(testdir)
    create_catalogue(testdir, "org.flathub.appstream_no_timestamp.xml")
    ret = rc(testdir, check_type, tmp_testdir)
    assert "appstream-release-tag-missing-timestamp" in set(ret["errors"])


def test_appstream_svg_screenshot(check_type: str, tmp_testdir: str) -> None:
    testdir = "tests/builddir/svg-screenshot"
    move_files(testdir)
    create_catalogue(testdir, "com.github.flathub.svg_screenshot.xml")
    ret = rc(testdir, check_type, tmp_testdir)
    assert "metainfo-svg-screenshots" in set(ret["errors"])


def test_eol_runtime(check_type: str, tmp_testdir: str) -> None:
    ret = rc("tests/builddir/eol_runtime", check_type, tmp_testdir)
    assert "runtime-is-eol-org.freedesktop.Platform-18.08" in set(ret["warnings"])


# ELF check is disabled for repo check
# in flatpak_builder_lint/checks/elfarch.py
def test_wrong_elf_arch(tmp_testdir: str) -> None:
    testdir = "tests/builddir/wrong-elf-arch"
    create_elf(testdir, "aarch64")
    create_elf(testdir, "riscv64", "test2.elf")
    ret = rc(testdir, "builddir", tmp_testdir)
    found_errors = set(ret["errors"])
    assert "elf-arch-multiple-found" in found_errors
    assert "elf-arch-not-found" in found_errors


def test_appstream_manifest_url_unreachable(
    check_type: str, tmp_testdir: str, mock_domainutils: dict[str, MagicMock]
) -> None:
    mock_domainutils["check_url"].return_value = (False, "Status: 404 | Body: Not Found")
    testdir = "tests/builddir/appstream-manifest-url-unreachable"
    move_files(testdir)
    create_catalogue(testdir, "org.flathub.appstream_manifest_url_unreachable.xml")
    ret = rc(testdir, check_type, tmp_testdir)
    assert "appstream-flathub-manifest-url-not-reachable" in set(ret["errors"])


def test_home_host_access(check_type: str, tmp_testdir: str) -> None:
    base_path = "tests/builddir/home_host"
    for i in range(1, 6):
        ret = rc(f"{base_path}/home_host{i}", check_type, tmp_testdir)
        assert "finish-args-home-filesystem-access" in set(ret["errors"])

    assert "finish-args-host-filesystem-access" in set(
        rc(f"{base_path}/home_host1", check_type, tmp_testdir)["errors"]
    )
    assert "finish-args-home-ro-filesystem-access" in set(
        rc(f"{base_path}/home_host6", check_type, tmp_testdir)["errors"]
    )
    assert "finish-args-host-ro-filesystem-access" in set(
        rc(f"{base_path}/home_host7", check_type, tmp_testdir)["errors"]
    )

    ret = rc(f"{base_path}/home_host_false", check_type, tmp_testdir)
    found_errors = set(ret["errors"])
    assert "finish-args-home-filesystem-access" not in found_errors
    assert "finish-args-host-filesystem-access" not in found_errors


def test_appstream_prerelease(check_type: str, tmp_testdir: str, monkeypatch: MonkeyPatch) -> None:
    testdir = "tests/builddir/appstream-prerelease"
    monkeypatch.setenv("REPO", "https://github.com/flathub/flathub")
    move_files(testdir)
    create_catalogue(testdir, "org.flathub.appstream_prerelease.xml")

    ret = rc(testdir, check_type, tmp_testdir)
    assert "appstream-latest-release-is-prerelease" in set(ret["errors"])

    monkeypatch.delenv("REPO", raising=False)
    ret = rc(testdir, check_type, tmp_testdir)
    assert "appstream-latest-release-is-prerelease" not in set(ret["errors"])
