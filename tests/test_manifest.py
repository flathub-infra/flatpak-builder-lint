import os
import shutil
import tempfile
from collections.abc import Generator

import pytest

from flatpak_builder_lint import checks, cli


@pytest.fixture(scope="module")
def tmp_testdir() -> Generator[str, None, None]:
    original_dir = os.getcwd()
    with tempfile.TemporaryDirectory() as tmpdir:
        targetdir = os.path.join(tmpdir, "tests", "manifests")
        shutil.copytree("tests/manifests", targetdir)
        yield tmpdir
    os.chdir(original_dir)


def run_checks(filename: str, testdir: str, enable_exceptions: bool = False) -> dict:
    os.chdir(testdir)
    checks.Check.errors = set()
    checks.Check.warnings = set()
    return cli.run_checks("manifest", filename, enable_exceptions)


def test_appid_too_few_cpts(tmp_testdir: str) -> None:
    ret = run_checks("tests/manifests/domain_checks/com.github.json", tmp_testdir)
    errors = set(ret["errors"])
    assert {"appid-less-than-3-components"} == errors


def test_appid_wrong_syntax(tmp_testdir: str) -> None:
    ret = run_checks("tests/manifests/domain_checks/com.--github--.flathub.json", tmp_testdir)
    errors = set(ret["errors"])
    assert {"appid-component-wrong-syntax"} == errors


def test_appid_too_many_cpts(tmp_testdir: str) -> None:
    ret = run_checks(
        "tests/manifests/domain_checks/org.gnome.gitlab.user.project.foo.bar.json", tmp_testdir
    )
    errors = set(ret["errors"])
    assert {"appid-too-many-components-for-app"} == errors


def test_appid_devel_skip(tmp_testdir: str) -> None:
    ret = run_checks("tests/manifests/domain_checks/ch.wwwwww.bar.Devel.json", tmp_testdir)
    assert "errors" not in ret


def test_appid_url_not_reachable(tmp_testdir: str) -> None:
    for i in (
        "tests/manifests/domain_checks/io.github.wwwwwwwwwwwww.bar.json",
        "tests/manifests/domain_checks/io.github.wwwwwwwwwwwww.foo.bar.json",
        "tests/manifests/domain_checks/io.github.ghost.bar.json",
        "tests/manifests/domain_checks/io.gitlab.wwwwwwwwwwwww.bar.json",
        "tests/manifests/domain_checks/io.sourceforge.wwwwwwwwwwwwwwww.bar.json",
        "tests/manifests/domain_checks/ch.wwwwww.bar.json",
        "tests/manifests/domain_checks/org.gnome.gitlab.wwwwwwwwwwwww.bar.json",
        "tests/manifests/domain_checks/org.freedesktop.gitlab.wwwwwwwwwwwww.bar.json",
        "tests/manifests/domain_checks/io.frama.wwwwwwwwwwwww.bar.json",
        "tests/manifests/domain_checks/page.codeberg.wwwwwwwwwwwww.foo.json",
    ):
        ret = run_checks(i, tmp_testdir)
        errors = set(ret["errors"])
        assert "appid-url-not-reachable" in errors


def test_appid_url_is_reachable(tmp_testdir: str) -> None:
    for i in (
        "tests/manifests/domain_checks/io.github.flatpak.flatpak.json",
        "tests/manifests/domain_checks/org.gnome.gitlab.YaLTeR.Identity.json",
        "tests/manifests/domain_checks/org.gnome.design.VectorSlicer.json",
        "tests/manifests/domain_checks/org.freedesktop.gitlab.drm_hwcomposer.drm-hwcomposer.json",
        "tests/manifests/domain_checks/io.frama.flopedt.FlOpEDT.json",
        # "tests/manifests/domain_checks/page.codeberg.forgejo.code-of-conduct.json",
        "tests/manifests/domain_checks/io.sourceforge.xampp.bar.json",
    ):
        ret = run_checks(i, tmp_testdir)
        assert "errors" not in ret


def test_appid_on_flathub(tmp_testdir: str) -> None:
    # encom.eu.org does not exist
    ret = run_checks("tests/manifests/domain_checks/org.eu.encom.spectral.json", tmp_testdir)
    assert "errors" not in ret


def test_appid_skip_domain_checks_extension(tmp_testdir: str) -> None:
    ret = run_checks(
        "tests/manifests/domain_checks/org.gtk.Gtk33theme.Helium-dark.json", tmp_testdir
    )
    assert "errors" not in ret


def test_appid_skip_domain_checks_baseapp(tmp_testdir: str) -> None:
    ret = run_checks(
        "tests/manifests/domain_checks/org.electronjs.Electron200.BaseApp.json", tmp_testdir
    )
    assert "errors" not in ret


def test_manifest_toplevel(tmp_testdir: str) -> None:
    errors = {
        "toplevel-no-command",
        "toplevel-cleanup-debug",
        "toplevel-no-modules",
    }

    not_founds = {
        "toplevel-no-command",
        "toplevel-unnecessary-branch",
    }

    ret = run_checks("tests/manifests/toplevel.json", tmp_testdir)
    found_errors = set(ret["errors"])

    assert errors.issubset(found_errors)
    assert "toplevel-unnecessary-branch" not in found_errors

    ret = run_checks("tests/manifests/base_app.json", tmp_testdir)
    found_errors = set(ret["errors"])

    for e in not_founds:
        assert e not in found_errors


def test_manifest_appid(tmp_testdir: str) -> None:
    errors = {
        "appid-filename-mismatch",
        "appid-uses-code-hosting-domain",
    }
    ret = run_checks("tests/manifests/appid.json", tmp_testdir)
    found_errors = set(ret["errors"])
    assert errors.issubset(found_errors)


def test_manifest_appid_too_few_cpts(tmp_testdir: str) -> None:
    errors = {
        "appid-code-hosting-too-few-components",
    }
    ret = run_checks("tests/manifests/appid-too-few-cpts.json", tmp_testdir)
    found_errors = set(ret["errors"])
    assert errors.issubset(found_errors)


def test_manifest_flathub_json(tmp_testdir: str) -> None:
    errors = {
        "flathub-json-skip-appstream-check",
        "flathub-json-modified-publish-delay",
    }

    ret = run_checks("tests/manifests/flathub_json.json", tmp_testdir)
    found_errors = set(ret["errors"])

    assert errors.issubset(found_errors)


def test_manifest_finish_args(tmp_testdir: str) -> None:
    errors = {
        "finish-args-arbitrary-dbus-access",
        "finish-args-flatpak-spawn-access",
        "finish-args-incorrect-dbus-gvfs",
        "finish-args-unnecessary-appid-own-name",
        "finish-args-wildcard-freedesktop-talk-name",
        "finish-args-wildcard-gnome-own-name",
        "finish-args-wildcard-kde-talk-name",
        "finish-args-portal-own-name",
        "finish-args-has-nodevice-dri",
        "finish-args-has-unshare-network",
        "finish-args-has-nosocket-cups",
        "finish-args-freedesktop-dbus-talk-name",
        "finish-args-freedesktop-dbus-system-talk-name",
        "finish-args-wildcard-kde-system-talk-name",
        "finish-args-x11-without-ipc",
        "finish-args-contains-both-x11-and-fallback",
        "finish-args-unnecessary-appid-talk-name",
    }

    expected_absents = {
        "finish-args-absolute-run-media-path",
        "finish-args-has-nodevice-shm",
        "finish-args-has-nosocket-fallback-x11",
    }

    ret = run_checks("tests/manifests/finish_args.json", tmp_testdir)
    found_errors = set(ret["errors"])

    assert errors.issubset(found_errors)
    for a in expected_absents:
        assert a not in found_errors
    for err in found_errors:
        assert not err.startswith(("finish-args-arbitrary-xdg-", "finish-args-unnecessary-xdg-"))


def test_manifest_finish_args_issue_wayland_x11(tmp_testdir: str) -> None:
    ret = run_checks("tests/manifests/finish_args-wayland-x11.json", tmp_testdir)
    found_errors = set(ret["errors"])
    assert "finish-args-contains-both-x11-and-wayland" in found_errors


def test_manifest_finish_args_incorrect_secret_talk_name(tmp_testdir: str) -> None:
    ret = run_checks("tests/manifests/finish_args-incorrect_secrets-talk-name.json", tmp_testdir)
    found_errors = set(ret["errors"])
    assert "finish-args-incorrect-secret-service-talk-name" in found_errors


def test_manifest_finish_args_issue_33(tmp_testdir: str) -> None:
    ret = run_checks("tests/manifests/own_name_substring.json", tmp_testdir)
    found_errors = set(ret["errors"])
    assert "finish-args-unnecessary-appid-own-name" not in found_errors

    ret = run_checks("tests/manifests/own_name_substring2.json", tmp_testdir)
    found_errors = set(ret["errors"])
    assert "finish-args-unnecessary-appid-own-name" in found_errors


def test_manifest_display_stuff(tmp_testdir: str) -> None:
    absents = {
        "finish-args-fallback-x11-without-wayland",
        "finish-args-only-wayland",
        "finish-args-contains-both-x11-and-wayland",
    }

    for file in (
        "display-supported2.json",
        "display-supported3.json",
    ):
        ret = run_checks(f"tests/manifests/{file}", tmp_testdir)
        found_errors = set(ret["errors"])
        for a in absents:
            assert a not in found_errors

    ret = run_checks("tests/manifests/display-only-wayland.json", tmp_testdir)
    found_errors = set(ret["errors"])
    assert "finish-args-only-wayland" in found_errors


def test_manifest_finish_args_empty(tmp_testdir: str) -> None:
    ret = run_checks("tests/manifests/finish_args_empty.json", tmp_testdir)
    found_errors = set(ret["errors"])
    assert "finish-args-not-defined" not in found_errors

    ret = run_checks("tests/manifests/finish_args_missing.json", tmp_testdir)
    found_errors = set(ret["errors"])
    assert "finish-args-not-defined" in found_errors


def test_manifest_modules(tmp_testdir: str) -> None:
    warnings = {
        "module-module1-buildsystem-is-plain-cmake",
        "module-module1-cmake-non-release-build",
        "module-module1-source-sha1-deprecated",
    }

    ret = run_checks("tests/manifests/modules.json", tmp_testdir)
    found_warnings = set(ret["warnings"])

    assert warnings.issubset(found_warnings)


def test_manifest_modules_git_allowed(tmp_testdir: str) -> None:
    ret = run_checks("tests/manifests/modules_git_allowed.json", tmp_testdir)
    found_errors = set(ret["errors"])
    assert not [x for x in found_errors if x.startswith("module-")]


def test_manifest_modules_git_disallowed(tmp_testdir: str) -> None:
    ret = run_checks("tests/manifests/modules_git_disallowed.json", tmp_testdir)
    errors = {
        "module-module1-source-git-no-url",
        "module-module2-source-git-no-url",
        "module-module3-source-git-url-not-http",
        "module-module4-source-git-no-tag-commit-branch",
        "module-module5-source-git-branch",
    }
    found_errors = set(ret["errors"])
    for e in errors:
        assert e in found_errors


def test_manifest_exceptions(tmp_testdir: str) -> None:
    ret = run_checks("tests/manifests/exceptions.json", tmp_testdir, enable_exceptions=True)
    found_errors = ret["errors"]
    found_warnings = ret.get("warnings", {})

    assert "appid-filename-mismatch" not in found_errors
    assert "toplevel-no-command" not in found_errors
    assert "flathub-json-deprecated-i386-arch-included" not in found_warnings


def test_manifest_exceptions_wildcard(tmp_testdir: str) -> None:
    ret = run_checks(
        "tests/manifests/exceptions_wildcard.json", tmp_testdir, enable_exceptions=True
    )
    assert ret == {}


def test_manifest_direct_dconf_access(tmp_testdir: str) -> None:
    ret = run_checks("tests/manifests/dconf.json", tmp_testdir)
    found_errors = ret["errors"]
    errors = {
        "finish-args-direct-dconf-path",
        "finish-args-dconf-talk-name",
        "finish-args-dconf-own-name",
    }
    for e in errors:
        assert e in found_errors


def test_manifest_xdg_dir_finish_arg(tmp_testdir: str) -> None:
    ret = run_checks("tests/manifests/xdg-dirs-access.json", tmp_testdir)
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
    found_errors = ret["errors"]
    for e in errors:
        assert e in found_errors


def test_manifest_nightly_checker(tmp_testdir: str) -> None:
    ret = run_checks("tests/manifests/module-nightly-x-checker.json", tmp_testdir)
    found_errors = ret["errors"]
    errors = {
        "module-module1-checker-tracks-commits",
    }
    for e in errors:
        assert e in found_errors
