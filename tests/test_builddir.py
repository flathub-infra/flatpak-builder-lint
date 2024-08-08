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
        assert not err.startswith(
            ("finish-args-arbitrary-xdg-", "finish-args-unnecessary-xdg-")
        )


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

    ret = run_checks("tests/builddir/flathub_json")
    found_errors = set(ret["errors"])

    assert errors.issubset(found_errors)


def test_builddir_baseapp() -> None:
    ret = run_checks("tests/builddir/baseapp")


def test_builddir_extension() -> None:
    ret = run_checks("tests/builddir/extension")


def test_builddir_console() -> None:
    errors = {
        "finish-args-not-defined",
        "desktop-file-exec-key-absent",
        "desktop-file-is-hidden",
        "desktop-file-terminal-key-not-true",
        "appid-url-not-reachable",
    }

    ret = run_checks("tests/builddir/console")
    found_errors = set(ret["errors"])

    assert "appstream-unsupported-component-type" not in found_errors
    assert errors == found_errors


def test_builddir_appstream_unsupported_ctype() -> None:

    ret = run_checks("tests/builddir/appstream-unsupported-ctype")
    found_errors = set(ret["errors"])

    assert "appstream-unsupported-component-type" in found_errors


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


def test_builddir_misplaced_icons() -> None:
    ret = run_checks("tests/builddir/misplaced-icons")
    errors = {
        "non-png-icon-in-hicolor-size-folder",
        "non-svg-icon-in-scalable-folder",
    }
    found_errors = set(ret["errors"])
    for err in errors:
        assert err in found_errors


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
    ret = run_checks("tests/builddir/appstream-broken-icon")
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
    ret = run_checks("tests/builddir/appstream-broken-remote-icon")
    found_errors = set(ret["errors"])
    errors = {
        "appstream-remote-icon-not-mirrored",
        "appstream-missing-categories",
    }
    for e in errors:
        assert e in found_errors
    assert "metainfo-launchable-tag-wrong-value" not in found_errors


def test_builddir_appstream_no_icon_file() -> None:
    ret = run_checks("tests/builddir/appstream-no-icon-file")
    found_errors = set(ret["errors"])
    assert "appstream-missing-icon-file" in found_errors


def test_builddir_appstream_icon_key_no_type() -> None:
    ret = run_checks("tests/builddir/appstream-icon-key-no-type")
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
        ret = run_checks(f"tests/builddir/min_success_metadata/{builddir}")
        assert "errors" not in ret

    ret = run_checks(f"tests/builddir/min_success_metadata/org.flathub.cli")
    found_errors = set(ret["errors"])
    # CLI applications are allowed to have no finish-args with exceptions
    accepted = {"finish-args-not-defined"}
    assert len(found_errors - accepted) == 0
    not_founds = {
        "appid-too-many-components-for-app",
        "metainfo-missing-launchable-tag",
        "appid-url-check-internal-error",
        "appid-url-not-reachable",
    }
    for n in not_founds:
        assert n not in found_errors


def test_builddir_aps_cid_mismatch_flatpak_id() -> None:
    ret = run_checks("tests/builddir/appstream-cid-mismatch-flatpak-id")
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
