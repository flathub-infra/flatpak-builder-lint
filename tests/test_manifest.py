from flatpak_builder_lint import checks, cli


def run_checks(filename: str, enable_exceptions: bool = False) -> dict:
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
    ret = run_checks(
        "tests/manifests/domain_checks/org.gnome.gitlab.user.project.foo.bar.json"
    )
    errors = set(ret["errors"])
    assert {"appid-too-many-components-for-app"} == errors


def test_appid_code_host_not_reachable() -> None:
    for i in (
        "tests/manifests/domain_checks/io.github.ghost.bar.json",
        "tests/manifests/domain_checks/io.github.ghost.foo.bar.json",
        "tests/manifests/domain_checks/org.freedesktop.gitlab.foo.bar.json",
        "tests/manifests/domain_checks/io.sourceforge.wwwwwwwwwwwwwwww.bar.json",
    ):
        ret = run_checks(i)
        errors = set(ret["errors"])
        assert {"appid-code-host-not-reachable"} == errors


def test_appid_code_host_is_reachable() -> None:
    for i in (
        "tests/manifests/domain_checks/io.github.flathub.flathub.json",
        "tests/manifests/domain_checks/org.gnome.gitlab.YaLTeR.Identity.json",
    ):
        ret = run_checks(i)
        assert "errors" not in ret


def test_appid_domain_or_ip_not_reachable() -> None:
    ret = run_checks("tests/manifests/domain_checks/ch.wwwwww.bar.json")
    errors = set(ret["errors"])
    assert {"appid-domain-not-resolvable"} == errors


def test_appid_domain_not_regd() -> None:
    ret = run_checks("tests/manifests/domain_checks/com.bla0.bar.json")
    errors = set(ret["errors"])
    assert {"appid-domain-not-registered"} == errors


def test_appid_on_flathub() -> None:
    ret = run_checks("tests/manifests/domain_checks/org.freedesktop.appstream.cli.json")
    info = set(ret["info"])
    assert "errors" not in ret
    assert "Domain check skipped, app is on Flathub" in info


def test_appid_skip_domain_checks_extension() -> None:
    ret = run_checks(
        "tests/manifests/domain_checks/io.github.ghost.foo.bar.extension.json"
    )
    info = set(ret["info"])
    assert "errors" not in ret
    assert "Domain check skipped for runtimes and baseapps" in info


def test_appid_skip_domain_checks_baseapp() -> None:
    ret = run_checks("tests/manifests/domain_checks/io.qt.coolbaseapp.BaseApp.json")
    info = set(ret["info"])
    assert "errors" not in ret
    assert "Domain check skipped for runtimes and baseapps" in info


def test_manifest_toplevel() -> None:
    errors = {
        "toplevel-no-command",
        "toplevel-cleanup-debug",
        "toplevel-no-modules",
    }
    warnings = {
        "toplevel-unnecessary-branch",
    }

    ret = run_checks("tests/manifests/toplevel.json")
    found_errors = set(ret["errors"])
    found_warnings = set(ret["warnings"])

    assert errors.issubset(found_errors)
    assert warnings.issubset(found_warnings)

    ret = run_checks("tests/manifests/base_app.json")
    found_errors = set(ret["errors"])

    assert "toplevel-no-command" not in found_errors


def test_manifest_appid() -> None:
    errors = {
        "appid-filename-mismatch",
        "appid-code-hosting-too-few-components",
        "appid-uses-code-hosting-domain",
    }
    ret = run_checks("tests/manifests/appid.json")
    found_errors = set(ret["errors"])
    assert errors.issubset(found_errors)


def test_manifest_flathub_json() -> None:
    errors = {
        "flathub-json-skip-appstream-check",
        "flathub-json-modified-publish-delay",
    }

    warnings = {"flathub-json-deprecated-i386-arch-included"}

    ret = run_checks("tests/manifests/flathub_json.json")
    found_errors = set(ret["errors"])
    found_warnings = set(ret["warnings"])

    assert errors.issubset(found_errors)
    assert warnings.issubset(found_warnings)


def test_manifest_finish_args() -> None:
    errors = {
        "finish-args-arbitrary-autostart-access",
        "finish-args-arbitrary-dbus-access",
        "finish-args-arbitrary-xdg-data-access",
        "finish-args-arbitrary-xdg-cache-access",
        "finish-args-flatpak-spawn-access",
        "finish-args-incorrect-dbus-gvfs",
        "finish-args-redundant-home-and-host",
        "finish-args-unnecessary-appid-own-name",
        "finish-args-unnecessary-xdg-data-access",
        "finish-args-wildcard-freedesktop-talk-name",
        "finish-args-wildcard-gnome-own-name",
        "finish-args-wildcard-kde-talk-name",
        "finish-args-portal-own-name",
        "finish-args-has-nodevice-dri",
        "finish-args-has-unshare-network",
        "finish-args-has-nosocket-cups",
    }

    warnings = {
        "finish-args-contains-both-x11-and-wayland",
        "finish-args-x11-without-ipc",
        "finish-args-redundant-device-all",
        "finish-args-contains-both-x11-and-fallback",
    }

    expected_absents = {
        "finish-args-absolute-run-media-path",
        "finish-args-has-nodevice-shm",
        "finish-args-has-nosocket-fallback-x11",
    }

    ret = run_checks("tests/manifests/finish_args.json")
    found_errors = set(ret["errors"])
    found_warnings = set(ret["warnings"])

    assert errors.issubset(found_errors)
    assert warnings.issubset(found_warnings)
    for a in expected_absents:
        assert a not in found_errors


def test_manifest_finish_args_issue_33() -> None:
    ret = run_checks("tests/manifests/own_name_substring.json")
    found_errors = set(ret["errors"])
    assert "finish-args-unnecessary-appid-own-name" not in found_errors

    ret = run_checks("tests/manifests/own_name_substring2.json")
    found_errors = set(ret["errors"])
    assert "finish-args-unnecessary-appid-own-name" in found_errors


def test_manifest_finish_args_shm() -> None:

    ret = run_checks("tests/manifests/finish-args-shm.json")
    found_warnings = set(ret["warnings"])

    assert "finish-args-deprecated-shm" in found_warnings


def test_manifest_finish_args_home_host() -> None:

    for file in (
        "finish_args-home_host1.json",
        "finish_args-home_host2.json",
    ):
        ret = run_checks(f"tests/manifests/{file}")
        found_errors = set(ret["errors"])
        assert "finish-args-redundant-home-and-host" in found_errors

    for file in (
        "finish_args-home_host3.json",
        "finish_args-home_host4.json",
    ):
        ret = run_checks(f"tests/manifests/{file}")
        found_errors = set(ret["errors"])
        assert "finish-args-redundant-home-and-host" not in found_errors


def test_manifest_display_stuff() -> None:

    absents = {
        "finish-args-fallback-x11-without-wayland",
        "finish-args-only-wayland",
    }

    for file in (
        "display-supported1.json",
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
        "module-module1-source-git-no-commit-or-tag",
        "module-module1-source-git-local-path",
        "module-module1-source-git-no-url",
        "module-module1-source-git-url-not-http",
    }

    warnings = {
        "module-module1-buildsystem-is-plain-cmake",
        "module-module1-cmake-non-release-build",
        "module-module2-autotools-redundant-prefix",
        "module-module1-cmake-redundant-prefix",
        "module-module1-source-sha1-deprecated",
    }

    ret = run_checks("tests/manifests/modules.json")
    found_errors = set(ret["errors"])
    found_warnings = set(ret["warnings"])

    assert errors.issubset(found_errors)
    assert warnings.issubset(found_warnings)


def test_manifest_modules_git_allowed() -> None:
    ret = run_checks("tests/manifests/modules_git_allowed.json")
    found_errors = set(ret["errors"])
    assert not [x for x in found_errors if x.startswith("module-")]


def test_manifest_modules_git_disallowed() -> None:
    ret = run_checks("tests/manifests/modules_git_disallowed.json")
    found_errors = set(ret["errors"])
    assert [x for x in found_errors if x.startswith("module-")]


def test_manifest_exceptions() -> None:
    ret = run_checks("tests/manifests/exceptions.json", enable_exceptions=True)
    found_errors = ret["errors"]
    found_warnings = ret.get("warnings", {})

    assert "appid-filename-mismatch" not in found_errors
    assert "toplevel-no-command" not in found_errors
    assert "flathub-json-deprecated-i386-arch-included" not in found_warnings


def test_manifest_exceptions_wildcard() -> None:
    ret = run_checks("tests/manifests/exceptions_wildcard.json", enable_exceptions=True)
    assert ret == {}
