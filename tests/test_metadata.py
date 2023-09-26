from flatpak_builder_lint import checks, cli


def run_checks(filename: str, enable_exceptions: bool = False) -> dict:
    checks.Check.errors = set()
    checks.Check.warnings = set()
    return cli.run_checks("build", filename, enable_exceptions)


def test_metadata_appid() -> None:
    errors = {
            'appid-ends-with-lowercase-desktop',
            'appid-uses-code-hosting-domain',
            'finish-args-not-defined'
            }
    ret = run_checks("tests/metadata/appid")
    found_errors = set(ret["errors"])
    assert errors.issubset(found_errors)


def test_metadata_finish_args() -> None:
    errors = {
        "finish-args-arbitrary-autostart-access",
        "finish-args-arbitrary-dbus-access",
        "finish-args-arbitrary-xdg-data-access",
        "finish-args-broken-kde-tray-permission",
        "finish-args-flatpak-spawn-access",
        "finish-args-incorrect-dbus-gvfs",
        "finish-args-redundant-home-and-host",
        "finish-args-unnecessary-appid-own-name",
        "finish-args-unnecessary-xdg-data-access",
    }

    warnings = {
        "finish-args-contains-both-x11-and-wayland",
        "finish-args-deprecated-shm",
        "finish-args-x11-without-ipc",
        "finish-args-redundant-device-all",
        "finish-args-contains-both-x11-and-fallback",
    }

    ret = run_checks("tests/metadata/finish_args")
    found_errors = set(ret["errors"])
    found_warnings = set(ret["warnings"])

    assert errors.issubset(found_errors)
    assert warnings.issubset(found_warnings)


def test_metadata_finish_args_missing() -> None:
     ret = run_checks("tests/metadata/finish_args_missing")
     found_errors = set(ret["errors"])
     assert "finish-args-not-defined" in found_errors
