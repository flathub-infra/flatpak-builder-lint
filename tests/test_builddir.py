from flatpak_builder_lint import checks, cli


def run_checks(filename: str) -> dict:
    checks.Check.errors = set()
    checks.Check.warnings = set()
    return cli.run_checks("builddir", filename)


def test_builddir_appid() -> None:
    errors = {"appid-ends-with-lowercase-desktop", "appid-uses-code-hosting-domain"}
    ret = run_checks("tests/builddir/appid")
    found_errors = set(ret["errors"])
    assert errors.issubset(found_errors)


def test_builddir_finish_args() -> None:
    errors = {
        "finish-args-arbitrary-autostart-access",
        "finish-args-arbitrary-dbus-access",
        "finish-args-arbitrary-xdg-data-access",
        "finish-args-flatpak-spawn-access",
        "finish-args-incorrect-dbus-gvfs",
        "finish-args-redundant-home-and-host",
        "finish-args-unnecessary-appid-own-name",
        "finish-args-unnecessary-xdg-data-access",
        "finish-args-wildcard-freedesktop-talk-name",
        "finish-args-wildcard-gnome-own-name",
        "finish-args-wildcard-kde-own-name",
        "finish-args-portal-talk-name",
        "finish-args-absolute-run-media-path",
        "finish-args-has-nodevice-dri",
        "finish-args-has-unshare-network",
        "finish-args-has-nosocket-cups",
    }

    warnings = {
        "finish-args-x11-without-ipc",
        "finish-args-redundant-device-all",
    }

    expected_absents = {
        "finish-args-has-nodevice-shm",
        "finish-args-has-nosocket-fallback-x11",
    }

    ret = run_checks("tests/builddir/finish_args")
    found_errors = set(ret["errors"])
    found_warnings = set(ret["warnings"])

    assert errors.issubset(found_errors)
    assert warnings.issubset(found_warnings)
    for a in expected_absents:
        assert a not in found_errors


def test_manifest_finish_args_shm() -> None:

    ret = run_checks("tests/builddir/finish_args_shm")
    found_warnings = set(ret["warnings"])

    assert "finish-args-deprecated-shm" in found_warnings


def test_builddir_display_supported() -> None:

    absents = {
        "finish-args-fallback-x11-without-wayland",
        "finish-args-only-wayland",
    }

    ret = run_checks("tests/builddir/display-supported")
    found_errors = set(ret["errors"])
    for a in absents:
        assert a not in found_errors


def test_manifest_finish_args_home_host() -> None:

    ret = run_checks(f"tests/builddir/finish_args_home_host")
    found_errors = set(ret["errors"])
    assert "finish-args-redundant-home-and-host" not in found_errors


def test_builddir_finish_args_missing() -> None:
    ret = run_checks("tests/builddir/finish_args_missing")
    found_errors = set(ret["errors"])
    assert "finish-args-not-defined" in found_errors


def test_builddir_flathub_json() -> None:
    errors = {
        "flathub-json-skip-appstream-check",
        "flathub-json-modified-publish-delay",
    }

    warnings = {"flathub-json-deprecated-i386-arch-included"}

    ret = run_checks("tests/builddir/flathub_json")
    found_errors = set(ret["errors"])
    found_warnings = set(ret["warnings"])

    assert errors.issubset(found_errors)
    assert warnings.issubset(found_warnings)


def test_builddir_baseapp() -> None:
    ret = run_checks("tests/builddir/baseapp")


def test_builddir_extension() -> None:
    ret = run_checks("tests/builddir/extension")


def test_builddir_console() -> None:
    errors = {
        "finish-args-not-defined",
        "appstream-unsupported-component-type",
        "appstream-metainfo-missing",
    }

    ret = run_checks("tests/builddir/console")
    found_errors = set(ret["errors"])

    assert errors == found_errors


def test_builddir_metadata_spaces() -> None:
    ret = run_checks("tests/builddir/metadata-spaces")


def test_builddir_desktop_file() -> None:
    ret = run_checks("tests/builddir/desktop-file")
    errors = {
        "desktop-file-icon-key-wrong-value",
        "desktop-file-is-hidden",
        "desktop-file-exec-has-flatpak-run",
        "desktop-file-icon-not-installed",
    }
    found_errors = set(ret["errors"])
    found_warnings = set(ret["warnings"])

    assert "desktop-file-low-quality-category" in found_warnings
    for err in errors:
        assert err in found_errors
    assert "appstream-missing-categories" not in found_errors


def test_builddir_quality_guidelines() -> None:
    ret = run_checks("tests/builddir/appdata-quality")
    errors = {
        "appstream-missing-developer-name",
        "appstream-missing-project-license",
        "no-exportable-icon-installed",
        "metainfo-missing-component-type",
        "appstream-launchable-file-missing",
    }
    warnings = {
        "appstream-name-too-long",
        "appstream-screenshot-missing-caption",
        "appstream-summary-too-long",
        "appstream-summary-ends-in-dot",
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
    ret = run_checks("tests/builddir/appstream-broken-icon")
    errors = {
        # Expected failure with appstreamcli validate
        "appstream-failed-validation",
        "no-exportable-icon-installed",
        "metainfo-launchable-tag-wrong-value",
        "finish-args-not-defined",
        "desktop-file-not-installed",
    }
    found_errors = set(ret["errors"])
    for e in errors:
        assert e in found_errors


def test_builddir_broken_remote_icon() -> None:
    ret = run_checks("tests/builddir/appstream-broken-remote-icon")
    found_errors = set(ret["errors"])
    errors = {
        "appstream-icon-key-no-type",
        "appstream-remote-icon-not-mirrored",
        "appstream-missing-icon-file",
        "appstream-missing-categories",
    }
    for e in errors:
        assert e in found_errors
    assert "metainfo-launchable-tag-wrong-value" not in found_errors


def test_min_success_metadata() -> None:

    # Illustrate the minimum metadata required to pass linter
    # These should not be broken
    for builddir in (
        "org.flathub.example.BaseApp",
        "org.flathub.example.extentsion",
        "org.flathub.example.gui",
    ):
        ret = run_checks(f"tests/builddir/min_success_metadata/{builddir}")
        assert "errors" not in ret

    ret = run_checks(f"tests/builddir/min_success_metadata/org.flathub.example.cli")
    found_errors = set(ret["errors"])
    # CLI applications are allowed to have no finish-args with exceptions
    accepted = {"finish-args-not-defined"}
    assert len(found_errors - accepted) == 0
    assert "metainfo-missing-launchable-tag" not in found_errors


def test_builddir_aps_cid_mismatch_flatpak_id() -> None:
    ret = run_checks("tests/builddir/appstream-cid-mismatch-flatpak-id")
    found_errors = set(ret["errors"])
    assert "appstream-id-mismatch-flatpak-id" in found_errors
