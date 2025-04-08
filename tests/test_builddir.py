import glob
import gzip
import os
import shutil
import struct
import tempfile
from collections.abc import Generator

import pytest

from flatpak_builder_lint import checks, cli


def create_catalogue(test_dir: str, xml_fname: str) -> None:
    cataloge_path = os.path.join(test_dir, "files/share/app-info/xmls")
    os.makedirs(test_dir, exist_ok=True)
    source_xml = os.path.join(cataloge_path, xml_fname)
    target_gzip = os.path.join(cataloge_path, xml_fname + ".gz")

    with open(source_xml, "rb") as xml_file, gzip.open(target_gzip, "wb") as gzip_file:
        gzip_file.write(xml_file.read())


def create_catalogue_icon(
    test_dir: str,
    icon_fname: str,
    size: str = "128x128",
) -> None:
    icon_dir = os.path.join(test_dir, f"files/share/app-info/icons/flatpak/{size}")
    os.makedirs(icon_dir, exist_ok=True)
    icon_path = os.path.join(icon_dir, icon_fname)

    with open(icon_path, "w", encoding="utf-8"):
        pass


def create_app_icon(
    test_dir: str,
    icon_fname: str,
    size: str = "128x128",
    scalable: bool = False,
    hicolor: bool = True,
) -> None:
    if scalable:
        icon_dir = os.path.join(test_dir, "files/share/icons/hicolor/scalable/apps")

    if hicolor:
        icon_dir = os.path.join(test_dir, f"files/share/icons/hicolor/{size}/apps")

    os.makedirs(icon_dir, exist_ok=True)
    icon_path = os.path.join(icon_dir, icon_fname)

    with open(icon_path, "w", encoding="utf-8"):
        pass


def create_file(path: str, fname: str) -> None:
    os.makedirs(path, exist_ok=True)
    file_path = os.path.join(path, fname)

    if os.path.exists(file_path):
        return

    with open(file_path, "w", encoding="utf-8"):
        pass


def create_elf(test_dir: str, arch: str, fname: str = "test.elf") -> None:
    dest = os.path.join(test_dir, "files/bin")
    os.makedirs(dest, exist_ok=True)

    archmap = {
        "x86_64": 0x3E,
        "aarch64": 0xB7,
        "riscv64": 0xF3,
    }

    if arch not in archmap:
        raise ValueError(f"Unsupported architecture: {arch}")

    elf_header = struct.pack(
        "<4s5B7x2H5I6Q",
        b"\x7fELF",
        2,
        1,
        1,
        0,
        0,
        2,
        archmap[arch],
        1,
        0x400000,
        0x40,
        0,
        0,
        64,
        0,
        0,
        0,
        0,
        0,
    )

    fpath = os.path.join(dest, fname)

    with open(fpath, "wb") as f:
        f.write(elf_header)


def move_files(testdir: str) -> None:
    paths = {
        "desktopfiles_path": os.path.join(testdir, "files/share/applications"),
        "cataloguefiles_path": os.path.join(testdir, "files/share/app-info/xmls"),
        "metainfofiles_path": os.path.join(testdir, "files/share/metainfo"),
        "flathubjson_path": os.path.join(testdir, "files"),
    }

    for path in paths.values():
        os.makedirs(path, exist_ok=True)

    flathubjson = os.path.join(testdir, "flathub.json")
    if os.path.exists(flathubjson) and os.path.isfile(flathubjson):
        shutil.move(flathubjson, paths["flathubjson_path"])

    for file in glob.glob(os.path.join(testdir, "*.desktop")):
        shutil.move(file, paths["desktopfiles_path"])

    for file in glob.glob(os.path.join(testdir, "*.xml")):
        if file.endswith((".metainfo.xml", ".appdata.xml")):
            shutil.move(file, paths["metainfofiles_path"])
        else:
            shutil.move(file, paths["cataloguefiles_path"])


@pytest.fixture(scope="module")
def tmp_testdir() -> Generator[str, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        targetdir = os.path.join(tmpdir, "tests", "builddir")
        shutil.copytree("tests/builddir", targetdir)
        yield tmpdir


@pytest.fixture(autouse=True)
def change_to_tmpdir(tmp_testdir: str) -> Generator[None, None, None]:
    original_dir = os.getcwd()
    os.chdir(tmp_testdir)
    yield
    os.chdir(original_dir)


def run_checks(filename: str) -> dict[str, str | list[str]]:
    checks.Check.errors = set()
    checks.Check.warnings = set()
    return cli.run_checks("builddir", filename)


def test_builddir_appid() -> None:
    errors = {"appid-ends-with-lowercase-desktop", "appid-uses-code-hosting-domain"}
    ret = run_checks("tests/builddir/appid")
    found_errors = set(ret["errors"])
    assert errors.issubset(found_errors)
    assert "appstream-metainfo-missing" in found_errors


def test_builddir_url_not_reachable() -> None:
    ret = run_checks("tests/builddir/wrong-rdns-appid")
    found_errors = set(ret["errors"])
    assert "appid-url-not-reachable" in found_errors


def test_builddir_finish_args() -> None:
    errors = {
        "finish-args-arbitrary-dbus-access",
        "finish-args-flatpak-spawn-access",
        "finish-args-incorrect-dbus-gvfs",
        "finish-args-unnecessary-appid-own-name",
        "finish-args-wildcard-freedesktop-talk-name",
        "finish-args-wildcard-gnome-own-name",
        "finish-args-wildcard-kde-own-name",
        "finish-args-portal-talk-name",
        "finish-args-absolute-run-media-path",
        "finish-args-has-nodevice-dri",
        "finish-args-has-unshare-network",
        "finish-args-has-nosocket-cups",
        "finish-args-freedesktop-dbus-talk-name",
        "finish-args-wildcard-gnome-system-own-name",
        "finish-args-freedesktop-dbus-system-talk-name",
        "finish-args-x11-without-ipc",
        "finish-args-flatpak-user-folder-access",
        "finish-args-host-tmp-access",
        "finish-args-flatpak-appdata-folder-access",
        "finish-args-host-var-access",
        "finish-args-mpris-flatpak-id-own-name",
        "finish-args-portal-impl-permissionstore-own-name",
        "finish-args-legacy-icon-folder-permission",
        "finish-args-legacy-font-folder-permission",
        "finish-args-incorrect-theme-folder-permission",
    }

    expected_absents = {
        "finish-args-has-nodevice-shm",
        "finish-args-has-nosocket-fallback-x11",
    }

    ret = run_checks("tests/builddir/finish_args")
    found_errors = set(ret["errors"])

    assert errors.issubset(found_errors)
    for a in expected_absents:
        assert a not in found_errors
    for err in found_errors:
        assert not err.startswith(("finish-args-arbitrary-xdg-", "finish-args-unnecessary-xdg-"))


def test_builddir_finish_args_new_metadata() -> None:
    ret = run_checks("tests/builddir/finish_args_new_metadata")
    found_errors = set(ret["errors"])
    assert "finish-args-no-required-flatpak" in found_errors


def test_builddir_display_supported() -> None:
    absents = {
        "finish-args-fallback-x11-without-wayland",
        "finish-args-only-wayland",
    }

    ret = run_checks("tests/builddir/display-supported")
    found_errors = set(ret["errors"])
    for a in absents:
        assert a not in found_errors


def test_builddir_finish_args_missing() -> None:
    ret = run_checks("tests/builddir/finish_args_missing")
    found_errors = set(ret["errors"])
    assert "finish-args-not-defined" in found_errors


def test_builddir_flathub_json() -> None:
    errors = {
        "flathub-json-skip-appstream-check",
        "flathub-json-modified-publish-delay",
    }
    testdir = "tests/builddir/flathub_json"
    move_files(testdir)
    ret = run_checks(testdir)
    found_errors = set(ret["errors"])

    assert errors.issubset(found_errors)


def test_builddir_console() -> None:
    errors = {
        "finish-args-not-defined",
        "desktop-file-exec-key-absent",
        "desktop-file-is-hidden",
        "desktop-file-terminal-key-not-true",
        "appid-url-not-reachable",
    }
    testdir = "tests/builddir/console"
    move_files(testdir)
    create_catalogue(testdir, "org.flathub.example.console.xml")
    ret = run_checks(testdir)
    found_errors = set(ret["errors"])

    assert "appstream-unsupported-component-type" not in found_errors
    assert errors == found_errors


def test_builddir_appstream_unsupported_ctype() -> None:
    testdir = "tests/builddir/appstream-unsupported-ctype"
    move_files(testdir)
    create_catalogue(testdir, "org.flathub.appstream_unsupported_ctype.xml")
    ret = run_checks(testdir)
    found_errors = set(ret["errors"])

    assert "appstream-unsupported-component-type" in found_errors


def test_builddir_metadata_spaces() -> None:
    run_checks("tests/builddir/metadata-spaces")


def test_builddir_desktop_file() -> None:
    testdir = "tests/builddir/desktop-file"
    move_files(testdir)
    icons = ["com.github.flathub_infra.desktop-file.Devel.png", "org.flathub.foo.png"]
    create_catalogue(testdir, "com.github.flathub_infra.desktop-file.xml")
    for i in icons:
        create_app_icon(testdir, i)
    ret = run_checks(testdir)
    errors = {
        "desktop-file-icon-key-wrong-value",
        "desktop-file-is-hidden",
        "desktop-file-exec-has-flatpak-run",
        "desktop-file-icon-not-installed",
    }
    found_errors = set(ret["errors"])
    found_warnings: set[str] = set(ret["warnings"])

    assert "desktop-file-low-quality-category" in found_warnings
    for err in errors:
        assert err in found_errors
    assert "appstream-missing-categories" not in found_errors


def test_builddir_misplaced_icons() -> None:
    testdir = "tests/builddir/misplaced-icons"
    move_files(testdir)
    create_catalogue(testdir, "org.flathub.example.misplaced-icons.xml")
    create_catalogue_icon(testdir, "org.flathub.example.misplaced-icons.png")
    create_app_icon(
        testdir, "org.flathub.example.misplaced-icons.png", scalable=True, hicolor=False
    )
    create_app_icon(testdir, "org.flathub.example.misplaced-icons.svg")
    ret = run_checks(testdir)
    errors = {
        "non-png-icon-in-hicolor-size-folder",
        "non-svg-icon-in-scalable-folder",
    }
    found_errors = set(ret["errors"])
    for err in errors:
        assert err in found_errors


def test_builddir_quality_guidelines() -> None:
    testdir = "tests/builddir/appdata-quality"
    move_files(testdir)
    create_catalogue(testdir, "com.github.flathub.appdata-quality.xml")
    create_app_icon(testdir, "foo")
    ret = run_checks(testdir)
    errors = {
        "appstream-missing-developer-name",
        "appstream-missing-project-license",
        "no-exportable-icon-installed",
        "appstream-launchable-file-missing",
    }
    warnings = {
        "appstream-screenshot-missing-caption",
    }
    found_warnings = set(ret["warnings"])
    found_errors = set(ret["errors"])
    for w in warnings:
        assert w in found_warnings
    for e in errors:
        assert e in found_errors
    # If present, it means a metainfo file that was validating
    # correctly broke and that should be fixed
    not_founds = {
        "appstream-failed-validation",
        "appstream-id-mismatch-flatpak-id",
        "metainfo-missing-launchable-tag",
    }
    for e in not_founds:
        assert e not in found_errors


def test_builddir_broken_icon() -> None:
    testdir = "tests/builddir/appstream-broken-icon"
    move_files(testdir)
    create_catalogue(testdir, "org.flathub.appstream_broken_icon.xml")
    create_file(os.path.join(testdir, "files/share/applications"), "org.foo.test.desktop")
    ret = run_checks(testdir)
    errors = {
        # Expected failure with appstreamcli validate
        "appstream-failed-validation",
        "no-exportable-icon-installed",
        "metainfo-launchable-tag-wrong-value",
        "finish-args-not-defined",
        "desktop-file-not-installed",
    }
    not_founds = {
        "appid-url-check-internal-error",
    }
    found_errors = set(ret["errors"])
    for e in errors:
        assert e in found_errors
    for n in not_founds:
        assert n not in found_errors


def test_builddir_broken_remote_icon() -> None:
    testdir = "tests/builddir/appstream-broken-remote-icon"
    move_files(testdir)
    create_catalogue(testdir, "org.flathub.appstream_broken_remote_icon.xml")
    create_catalogue_icon(testdir, "org.flathub.appstream_broken_remote_icon.png")
    ret = run_checks(testdir)
    found_errors = set(ret["errors"])
    errors = {
        "appstream-remote-icon-not-mirrored",
        "appstream-missing-categories",
    }
    for e in errors:
        assert e in found_errors
    assert "metainfo-launchable-tag-wrong-value" not in found_errors


def test_builddir_appstream_no_icon_file() -> None:
    testdir = "tests/builddir/appstream-no-icon-file"
    move_files(testdir)
    create_catalogue(testdir, "org.flathub.appstream_no_icon_file.xml")
    ret = run_checks(testdir)
    found_errors = set(ret["errors"])
    assert "appstream-missing-icon-file" in found_errors


def test_builddir_appstream_icon_key_no_type() -> None:
    testdir = "tests/builddir/appstream-icon-key-no-type"
    move_files(testdir)
    create_catalogue(testdir, "org.flathub.appstream_icon_key_no_type.xml")
    create_catalogue_icon(testdir, "org.flathub.appstream_icon_key_no_type.png")
    ret = run_checks(testdir)
    found_errors = set(ret["errors"])
    assert "appstream-icon-key-no-type" in found_errors


def test_min_success_metadata() -> None:
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

        ret = run_checks(testdir)
        assert "errors" not in ret

    cli_testdir = "tests/builddir/min_success_metadata/org.flathub.cli"
    move_files(cli_testdir)
    create_catalogue(cli_testdir, "org.flathub.cli.xml")
    ret = run_checks(cli_testdir)
    found_errors = set(ret["errors"])
    # CLI applications are allowed to have no finish-args with exceptions
    accepted = {"finish-args-not-defined"}
    assert len(found_errors - accepted) == 0
    not_founds = {
        "appid-too-many-components-for-app",
        "metainfo-missing-launchable-tag",
        "appid-url-check-internal-error",
        "appid-url-not-reachable",
        "appstream-no-flathub-manifest-key",
        "appstream-flathub-manifest-url-not-reachable",
    }
    for n in not_founds:
        assert n not in found_errors


def test_builddir_aps_cid_mismatch_flatpak_id() -> None:
    testdir = "tests/builddir/appstream-cid-mismatch-flatpak-id"
    move_files(testdir)
    create_catalogue(testdir, "org.flathub.appstream-cid-mismatch-flatpak-id.xml")
    ret = run_checks(testdir)
    found_errors = set(ret["errors"])
    assert "appstream-id-mismatch-flatpak-id" in found_errors


def test_builddir_dconf_access() -> None:
    ret = run_checks("tests/builddir/dconf-access")
    found_errors = set(ret["errors"])
    errors = {
        "finish-args-dconf-talk-name",
        "finish-args-direct-dconf-path",
    }
    for e in errors:
        assert e in found_errors


def test_builddir_xdg_dir_access() -> None:
    ret = run_checks("tests/builddir/finish_args_xdg_dirs")
    found_errors = set(ret["errors"])
    errors = {
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
    }
    for e in errors:
        assert e in found_errors


def test_builddir_appstream_missing_timestamp() -> None:
    testdir = "tests/builddir/appstream-missing-timestamp"
    move_files(testdir)
    create_catalogue(testdir, "org.flathub.appstream_no_timestamp.xml")
    ret = run_checks(testdir)
    found_errors = set(ret["errors"])
    assert "appstream-release-tag-missing-timestamp" in found_errors


def test_builddir_appstream_svg_screenshot() -> None:
    testdir = "tests/builddir/svg-screenshot"
    move_files(testdir)
    create_catalogue(testdir, "com.github.flathub.svg_screenshot.xml")
    ret = run_checks(testdir)
    found_errors = set(ret["errors"])
    assert "metainfo-svg-screenshots" in found_errors


def test_builddir_eol_runtime() -> None:
    testdir = "tests/builddir/eol_runtime"
    ret = run_checks(testdir)
    found_warnings = set(ret["warnings"])
    assert "runtime-is-eol-org.freedesktop.Platform-18.08" in found_warnings


def test_builddir_wrong_elf_arch() -> None:
    testdir = "tests/builddir/wrong-elf-arch"
    create_elf(testdir, "aarch64")
    create_elf(testdir, "riscv64", "test2.elf")
    ret = run_checks(testdir)
    found_errors = set(ret["errors"])
    errors = {
        "elf-arch-multiple-found",
        "elf-arch-not-found",
    }
    for e in errors:
        assert e in found_errors


def test_builddir_appstream_manifest_url_unreachable() -> None:
    testdir = "tests/builddir/appstream-manifest-url-unreachable"
    move_files(testdir)
    create_catalogue(testdir, "org.flathub.appstream_manifest_url_unreachable.xml")
    ret = run_checks(testdir)
    found_errors = set(ret["errors"])
    assert "appstream-flathub-manifest-url-not-reachable" in found_errors
