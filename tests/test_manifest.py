import os
import shutil
import subprocess
import tempfile
from collections.abc import Generator

import pytest
from _pytest.monkeypatch import MonkeyPatch

from flatpak_builder_lint import checks, cli


def create_git_repo(path: str) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=path, check=True)
    subprocess.run(
        [
            "git",
            "remote",
            "add",
            "origin",
            "https://github.com/flathub-infra/flatpak-builder-lint.git",
        ],
        cwd=path,
        check=True,
    )


def set_git_remote_url(path: str, new_url: str) -> None:
    subprocess.run(["git", "remote", "remove", "origin"], cwd=path, check=False)
    subprocess.run(["git", "remote", "add", "origin", new_url], cwd=path, check=True)


def create_file(path: str, size_mb: int = 10) -> None:
    filepath = os.path.join(path, "file.txt")
    with open(filepath, "wb") as f:
        f.seek(size_mb * 1024 * 1024 - 1)
        f.write(b"\0")


@pytest.fixture(scope="module")
def tmp_testdir() -> Generator[str, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        targetdir = os.path.join(tmpdir, "tests", "manifests")
        shutil.copytree("tests/manifests", targetdir, symlinks=True)
        yield tmpdir


@pytest.fixture(autouse=True)
def change_to_tmpdir(tmp_testdir: str) -> Generator[None, None, None]:
    original_dir = os.getcwd()
    os.chdir(tmp_testdir)
    yield
    os.chdir(original_dir)


def run_checks(filename: str, enable_exceptions: bool = False) -> dict[str, str | list[str]]:
    checks.Check.errors = set()
    checks.Check.warnings = set()
    return cli.run_checks("manifest", filename, enable_exceptions)


def test_appid_too_few_cpts() -> None:
    ret = run_checks("tests/manifests/domain_checks/com.github.json")
    errors = set(ret["errors"])
    assert {"appid-less-than-3-components"} == errors


def test_appid_wrong_syntax() -> None:
    ret = run_checks("tests/manifests/domain_checks/com.--github--.flathub.json")
    errors = set(ret["errors"])
    assert {"appid-component-wrong-syntax"} == errors


def test_appid_too_many_cpts() -> None:
    ret = run_checks("tests/manifests/domain_checks/org.gnome.gitlab.user.project.foo.bar.json")
    errors = set(ret["errors"])
    assert {"appid-too-many-components-for-app"} == errors


def test_appid_url_not_reachable() -> None:
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
        ret = run_checks(i)
        errors = set(ret["errors"])
        assert "appid-url-not-reachable" in errors


def test_appid_url_is_reachable() -> None:
    for i in (
        "tests/manifests/domain_checks/io.github.flatpak.flatpak.json",
        "tests/manifests/domain_checks/org.gnome.gitlab.YaLTeR.Identity.json",
        "tests/manifests/domain_checks/org.gnome.design.VectorSlicer.json",
        # "tests/manifests/domain_checks/org.freedesktop.gitlab.drm_hwcomposer.drm-hwcomposer.json",
        # "tests/manifests/domain_checks/io.frama.flopedt.FlOpEDT.json",
        "tests/manifests/domain_checks/page.codeberg.forgejo.code-of-conduct.json",
        #        "tests/manifests/domain_checks/io.sourceforge.xampp.bar.json",
    ):
        ret = run_checks(i)
        assert "errors" not in ret


def test_appid_on_flathub() -> None:
    # encom.eu.org does not exist
    ret = run_checks("tests/manifests/domain_checks/org.eu.encom.spectral.json")
    assert "errors" not in ret


def test_appid_skip_domain_checks_extension() -> None:
    ret = run_checks("tests/manifests/domain_checks/org.gtk.Gtk33theme.Helium-dark.json")
    assert "errors" not in ret


def test_appid_skip_domain_checks_baseapp() -> None:
    ret = run_checks("tests/manifests/domain_checks/org.electronjs.Electron200.BaseApp.json")
    assert "errors" not in ret


def test_manifest_toplevel() -> None:
    errors = {
        "toplevel-no-command",
        "toplevel-cleanup-debug",
        "toplevel-no-modules",
    }

    not_founds = {
        "toplevel-no-command",
        "toplevel-unnecessary-branch",
    }

    ret = run_checks("tests/manifests/toplevel.json")
    found_errors = set(ret["errors"])

    assert errors.issubset(found_errors)

    ret = run_checks("tests/manifests/base_app.json")
    found_errors = set(ret["errors"])

    for e in not_founds:
        assert e not in found_errors

    assert "toplevel-cleanup-debug" in found_errors


def test_manifest_appid() -> None:
    errors = {
        "appid-filename-mismatch",
        "appid-uses-code-hosting-domain",
    }
    ret = run_checks("tests/manifests/appid.json")
    found_errors = set(ret["errors"])
    assert errors.issubset(found_errors)


def test_manifest_appid_too_few_cpts() -> None:
    errors = {
        "appid-code-hosting-too-few-components",
    }
    ret = run_checks("tests/manifests/appid-too-few-cpts.json")
    found_errors = set(ret["errors"])
    assert errors.issubset(found_errors)


def test_manifest_flathub_json() -> None:
    errors = {
        "flathub-json-skip-appstream-check",
    }

    ret = run_checks("tests/manifests/flathub_json.json")
    found_errors = set(ret["errors"])

    assert errors.issubset(found_errors)


def test_manifest_finish_args() -> None:
    errors = {
        "finish-args-arbitrary-dbus-access",
        "finish-args-flatpak-spawn-access",
        "finish-args-incorrect-dbus-gvfs",
        "finish-args-wildcard-freedesktop-talk-name",
        "finish-args-wildcard-kde-talk-name",
        "finish-args-has-nodevice-dri",
        "finish-args-has-unshare-network",
        "finish-args-has-nosocket-cups",
        "finish-args-freedesktop-dbus-talk-name",
        "finish-args-freedesktop-dbus-system-talk-name",
        "finish-args-wildcard-kde-system-talk-name",
        "finish-args-x11-without-ipc",
        "finish-args-contains-both-x11-and-fallback",
        "finish-args-unnecessary-appid-talk-name",
        "finish-args-flatpak-system-folder-access",
        "finish-args-host-tmp-access",
        "finish-args-host-var-access",
        "finish-args-flatpak-appdata-folder-access",
        "finish-args-portal-impl-permissionstore-talk-name",
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
        "finish-args-systemd1-talk-name",
        "finish-args-plasmashell-system-talk-name",
        "finish-args-own-name-org.freedesktop.portal.Foo",
        "finish-args-system-own-name-org.freedesktop.login1",
        "finish-args-own-name-wildcard-org.gnome",
        "finish-args-own-name-org.kde.StatusNotifierItem",
        "finish-args-own-name-org.kde.KWin",
        "finish-args-full-home-cache-access",
        "finish-args-full-home-local-access",
        "finish-args-host-root-filesystem-access",
    }

    expected_absents = {
        "finish-args-absolute-run-media-path",
        "finish-args-has-nodevice-shm",
        "finish-args-has-nosocket-fallback-x11",
        "finish-args-no-required-flatpak",
        "finish-args-insufficient-required-flatpak",
        "finish-args-own-name-org.flathub.finish_args",
        "finish-args-own-name-org.mpris.MediaPlayer2.org.flathub.finish_args",
    }

    ret = run_checks("tests/manifests/finish_args.json")
    found_errors = set(ret["errors"])

    assert errors.issubset(found_errors)
    for a in expected_absents:
        assert a not in found_errors
    for err in found_errors:
        assert not err.startswith(("finish-args-arbitrary-xdg-", "finish-args-unnecessary-xdg-"))


def test_manifest_finish_args_fs_negative() -> None:
    ret = run_checks("tests/manifests/finish_args_fs_negative.json")
    found_errors = set(ret["errors"])
    absents = {
        "finish-args-full-home-config-access",
        "finish-args-full-home-cache-access",
        "finish-args-full-home-local-access",
        "finish-args-full-home-local-share-access",
        "finish-args-autostart-filesystem-access",
        "finish-args-desktopfile-filesystem-access",
    }
    for err in absents:
        assert err not in found_errors


def test_manifest_finish_args_new_metadata() -> None:
    ret = run_checks("tests/manifests/finish_args-new-metadata.json")
    found_errors = set(ret["errors"])
    errors = {
        "finish-args-insufficient-required-flatpak",
        "finish-args-has-dev-input",
    }
    for err in errors:
        assert err in found_errors


def test_manifest_finish_args_issue_wayland_x11() -> None:
    ret = run_checks("tests/manifests/finish_args-wayland-x11.json")
    found_errors = set(ret["errors"])
    assert "finish-args-contains-both-x11-and-wayland" in found_errors


def test_manifest_finish_args_incorrect_secret_talk_name() -> None:
    ret = run_checks("tests/manifests/finish_args-incorrect_secrets-talk-name.json")
    found_errors = set(ret["errors"])
    assert "finish-args-incorrect-secret-service-talk-name" in found_errors


def test_manifest_display_stuff() -> None:
    absents = {
        "finish-args-fallback-x11-without-wayland",
        "finish-args-only-wayland",
        "finish-args-contains-both-x11-and-wayland",
    }

    for file in (
        "display-supported2.json",
        "display-supported3.json",
    ):
        ret = run_checks(f"tests/manifests/{file}")
        found_errors = set(ret["errors"])
        for a in absents:
            assert a not in found_errors

    ret = run_checks("tests/manifests/display-only-wayland.json")
    found_errors = set(ret["errors"])
    assert "finish-args-only-wayland" in found_errors


def test_manifest_finish_args_empty() -> None:
    ret = run_checks("tests/manifests/finish_args_empty.json")
    found_errors = set(ret["errors"])
    assert "finish-args-not-defined" not in found_errors

    ret = run_checks("tests/manifests/finish_args_missing.json")
    found_errors = set(ret["errors"])
    assert "finish-args-not-defined" in found_errors


def test_manifest_modules() -> None:
    errors = {
        "module-module1-source-sha1-deprecated",
        "module-module1-cleanup-debug",
    }

    ret = run_checks("tests/manifests/modules.json")
    found_errors = set(ret["errors"])

    assert "appid-unprefixed-bundled-extension-org.flathub.example.BundledExtension" in found_errors
    assert (
        "appid-unprefixed-bundled-extension-org.flathub.modules.BundledExtension"
        not in found_errors
    )
    for i in errors:
        assert i in found_errors


def test_manifest_modules_git_allowed() -> None:
    ret = run_checks("tests/manifests/modules_git_allowed.json")
    found_errors = set(ret["errors"])
    assert not [x for x in found_errors if x.startswith("module-")]


def test_manifest_modules_git_disallowed() -> None:
    ret = run_checks("tests/manifests/modules_git_disallowed.json")
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


def test_manifest_exceptions() -> None:
    ret = run_checks("tests/manifests/exceptions.json", enable_exceptions=True)
    found_errors = ret["errors"]
    found_warnings = ret.get("warnings", [])

    assert "appid-filename-mismatch" not in found_errors
    assert "toplevel-no-command" not in found_errors
    assert "flathub-json-deprecated-i386-arch-included" not in found_warnings


def test_manifest_exceptions_wildcard() -> None:
    ret = run_checks("tests/manifests/exceptions_wildcard.json", enable_exceptions=True)
    assert ret == {}


def test_manifest_direct_dconf_access() -> None:
    ret = run_checks("tests/manifests/dconf.json")
    found_errors = ret["errors"]
    errors = {
        "finish-args-direct-dconf-path",
        "finish-args-dconf-talk-name",
    }
    for e in errors:
        assert e in found_errors


def test_manifest_xdg_dir_finish_arg() -> None:
    ret = run_checks("tests/manifests/xdg-dirs-access.json")
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


def test_manifest_nightly_checker() -> None:
    ret = run_checks("tests/manifests/module-nightly-x-checker.json")
    found_errors = ret["errors"]
    errors = {
        "module-module1-checker-tracks-commits",
    }
    for e in errors:
        assert e in found_errors


def test_manifest_symlink() -> None:
    ret = run_checks("tests/manifests/symlinks/symlink.json")
    found_errors = ret["errors"]
    assert "manifest-file-is-symlink" in found_errors
    ret = run_checks("tests/manifests/symlinks/source.json")
    found_errors = ret["errors"]
    assert "manifest-file-is-symlink" not in found_errors


def test_manifest_eol_runtime() -> None:
    ret = run_checks("tests/manifests/eol_runtime.json")
    found_warnings = ret["warnings"]
    assert "runtime-is-eol-org.gnome.Sdk-40" in found_warnings


def test_manifest_in_git_repo(tmp_testdir: str) -> None:
    repo_path = os.path.abspath(os.path.join(tmp_testdir, "tests", "manifests", "git-repo-checks"))
    create_file(repo_path, 30)
    create_git_repo(repo_path)
    ret = run_checks("tests/manifests/git-repo-checks/git-repo-checks.json")
    found_errors = set(ret["errors"])
    errors = {
        "external-gitmodule-url-found",
        "manifest-directory-too-large",
    }
    for err in errors:
        assert err in found_errors

    from flatpak_builder_lint import gitutils, manifest

    manifest.show_manifest.cache_clear()
    gitutils.is_git_directory.cache_clear()
    gitutils.get_git_toplevel.cache_clear()
    gitutils.get_github_repo_namespace.cache_clear()
    gitutils.get_repo_tree_size.cache_clear()

    set_git_remote_url(repo_path, "https://example.org/foobar.git")
    ret = run_checks("tests/manifests/git-repo-checks/git-repo-checks.json")
    found_errors = set(ret["errors"])
    for err in errors:
        assert err not in found_errors


def test_manifest_unknown_properties() -> None:
    ret = run_checks("tests/manifests/unknown-properties-1.json")
    found_errors = ret["errors"]
    assert "manifest-unknown-properties" in found_errors
    ret = run_checks("tests/manifests/unknown-properties-2.json")
    found_errors = ret["errors"]
    assert "manifest-unknown-properties" not in found_errors


def test_manifest_json_warnings() -> None:
    ret = run_checks("tests/manifests/com.example.json_warnings.json")
    found_errors = ret["errors"]
    assert "manifest-json-warnings" in found_errors


def test_manifest_yaml() -> None:
    ret = run_checks("tests/manifests/yaml/manfiest-invalid.yml")
    found_errors = ret["errors"]
    assert "manifest-invalid-yaml" in found_errors
    ret = run_checks("tests/manifests/yaml/manfiest-valid.yml")
    found_errors = ret["errors"]
    assert "manifest-invalid-yaml" not in found_errors


def test_manifest_build_network_access(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("REPO", "https://github.com/flathub/org.flatpak.Builder")
    ret = run_checks("tests/manifests/network_access.json")
    found_errors = ret["errors"]
    errors = {
        "manifest-toplevel-build-network-access",
        "module-abracadabra-build-network-access",
    }
    for e in errors:
        assert e in found_errors


def test_manifest_home_host_access() -> None:
    base_path = "tests/manifests/home_host"
    for i in range(1, 6):
        ret = run_checks(f"{base_path}/org.flathub.home_host{i}.json")
        found_errors = set(ret["errors"])
        assert "finish-args-home-filesystem-access" in found_errors

    ret = run_checks(f"{base_path}/org.flathub.home_host1.json")
    found_errors = set(ret["errors"])
    assert "finish-args-host-filesystem-access" in found_errors

    ret = run_checks(f"{base_path}/org.flathub.home_host6.json")
    found_errors = set(ret["errors"])
    assert "finish-args-home-ro-filesystem-access" in found_errors

    ret = run_checks(f"{base_path}/org.flathub.home_host7.json")
    found_errors = set(ret["errors"])
    assert "finish-args-host-ro-filesystem-access" in found_errors

    ret = run_checks(f"{base_path}/org.flathub.home_host_false.json")
    found_errors = set(ret["errors"])
    for e in ("finish-args-home-filesystem-access", "finish-args-host-filesystem-access"):
        assert e not in found_errors
