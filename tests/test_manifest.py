from flatpak_builder_lint.cli import run_checks


def test_toplevel() -> None:
    errors = {
        "toplevel-no-command",
        "toplevel-cleanup-debug",
        "toplevel-no-modules",
    }
    warnings = {
        "toplevel-unecessary-branch",
    }

    ret = run_checks("tests/manifests/toplevel.json")
    found_errors = set(ret["errors"])
    found_warnings = set(ret["warnings"])

    assert errors.issubset(found_errors)
    assert warnings.issubset(found_warnings)


def test_appid() -> None:
    errors = {
        "appid-filename-mismatch",
        "appid-code-hosting-too-few-components",
        "appid-uses-code-hosting-domain",
    }
    ret = run_checks("tests/manifests/appid.json")
    found_errors = set(ret["errors"])
    assert errors.issubset(found_errors)


def test_flathub_json() -> None:
    errors = {
        "flathub-json-skip-appstream-check",
        "flathub-json-eol-rebase-misses-new-id",
        "flathub-json-modified-publish-delay",
    }

    warnings = {"flathub-json-deprecated-i386-arch-included"}

    ret = run_checks("tests/manifests/flathub_json.json")
    found_errors = set(ret["errors"])
    found_warnings = set(ret["warnings"])

    assert errors.issubset(found_errors)
    assert warnings.issubset(found_warnings)


def test_finish_args() -> None:
    errors = {
        "finish-args-arbitrary-autostart-access",
        "finish-args-arbitrary-xdg-data-access",
        "finish-args-broken-kde-tray-permission",
        "finish-args-flatpak-spawn-access",
        "finish-args-incorrect-dbus-gvfs",
        "finish-args-redundant-device-all",
        "finish-args-redundant-home-and-host",
        "finish-args-unnecessary-appid-own-name",
        "finish-args-unnecessary-xdg-data-access",
    }

    warnings = {
        "finish-args-contains-both-x11-and-wayland",
        "finish-args-deprecated-shm",
        "finish-args-x11-without-ipc",
    }

    ret = run_checks("tests/manifests/finish_args.json")
    found_errors = set(ret["errors"])
    found_warnings = set(ret["warnings"])

    assert errors.issubset(found_errors)
    assert warnings.issubset(found_warnings)


def test_modules() -> None:
    errors = {
        "module-module1-source-git-no-commit-or-tag",
        "module-module1-source-git-local-path",
        "module-module1-source-git-no-url",
        "module-module1-source-git-url-not-http",
    }

    warnings = {
        "module-module1-buildsystem-is-plain-cmake",
        "module-module1-cmake-no-debuginfo",
        "module-module2-autotools-redundant-prefix",
        "module-module1-cmake-redundant-prefix",
        "module-module1-source-sha1-deprecated",
    }

    ret = run_checks("tests/manifests/modules.json")
    found_errors = set(ret["errors"])
    found_warnings = set(ret["warnings"])

    assert errors.issubset(found_errors)
    assert warnings.issubset(found_warnings)


def test_exceptions() -> None:
    ret = run_checks("tests/manifests/exceptions.json", enable_exceptions=True)
    found_errors = ret["errors"]
    found_warnings = ret["warnings"]

    assert "appid-filename-mismatch" not in found_errors
    assert "toplevel-no-command" not in found_errors
    assert "flathub-json-deprecated-i386-arch-included" not in found_warnings


def test_exceptions_wildcard() -> None:
    ret = run_checks("tests/manifests/exceptions_wildcard.json", enable_exceptions=True)
    assert ret == {}
