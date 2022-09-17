from flatpak_builder_lint.cli import run_checks


def test_toplevel() -> None:
    errors = {
        "toplevel-no-command",
        "toplevel-unecessary-branch",
        "toplevel-unecessary-default-branch",
        "toplevel-cleanup-debug",
        "toplevel-no-modules",
    }

    ret = run_checks("tests/manifests/toplevel.json")
    found_errors = set(ret["errors"])
    assert errors.issubset(found_errors)


def test_appid() -> None:
    errors = {"appid-filename-mismatch", "appid-code-hosting-too-few-components"}

    warnings = {"appid-uses-code-hosting-domain"}

    ret = run_checks("tests/manifests/appid.json")
    found_errors = set(ret["errors"])
    found_warnings = set(ret["warnings"])

    assert errors.issubset(found_errors)
    assert warnings.issubset(found_warnings)


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
        "finish-args-contains-both-x11-and-wayland",
        "finish-args-x11-without-ipc",
        "finish-args-arbitrary-xdg-data-access",
        "finish-args-unnecessary-xdg-data-access",
        "finish-args-redundant-home-and-host",
        "finish-args-unnecessary-appid-own-name",
        "finish-args-broken-kde-tray-permission",
        "finish-args-arbitrary-autostart-access",
        "finish-args-incorrect-dbus-gvfs",
        "finish-args-redundant-device-all",
    }

    warnings = {"finish-args-deprecated-shm"}

    ret = run_checks("tests/manifests/finish_args.json")
    found_errors = set(ret["errors"])
    found_warnings = set(ret["warnings"])

    assert errors.issubset(found_errors)
    assert warnings.issubset(found_warnings)


def test_modules() -> None:
    errors = {
        "module-module1-cmake-redundant-prefix",
        "module-module1-source-git-no-commit-or-tag",
        "module-module1-source-git-local-path",
        "module-module1-source-git-no-url",
        "module-module1-source-git-url-not-http",
        "module-module1-source-sha1-deprecated",
        "module-module2-autotools-redundant-prefix",
        "module-module2-no-sources",
    }

    warnings = {
        "module-module1-buildsystem-is-plain-cmake",
        "module-module1-cmake-no-debuginfo",
    }

    ret = run_checks("tests/manifests/modules.json")
    found_errors = set(ret["errors"])
    found_warnings = set(ret["warnings"])

    assert errors.issubset(found_errors)
    assert warnings.issubset(found_warnings)


def test_exceptions() -> None:
    ret = run_checks("tests/manifests/exceptions.json")
    found_errors = set(ret["errors"])
    found_warnings = set(ret["warnings"])

    assert "appid-filename-mismatch" not in found_errors
    assert "toplevel-no-command" not in found_errors
    assert "flathub-json-deprecated-i386-arch-included" not in found_warnings
