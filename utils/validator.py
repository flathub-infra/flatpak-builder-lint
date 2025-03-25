import argparse
import json
import os
from collections.abc import Sequence

KNOWN_EXCEPTIONS = {
    "appid-code-hosting-too-few-components",
    "appid-ends-with-lowercase-desktop",
    "appid-uses-code-hosting-domain",
    "appstream-failed-validation",
    "appstream-id-mismatch-flatpak-id",
    "appstream-missing-developer-name",
    "desktop-file-failed-validation",
    "finish-args-arbitrary-autostart-access",
    "finish-args-arbitrary-dbus-access",
    "finish-args-contains-both-x11-and-wayland",
    "finish-args-flatpak-spawn-access",
    "finish-args-not-defined",
    "finish-args-wildcard-kde-own-name",
    "flathub-json-modified-publish-delay",
    "finish-args-wildcard-kde-talk-name",
    "flathub-json-automerge-enabled",
    "appid-too-many-components-for-app",
    "finish-args-direct-dconf-path",
    "finish-args-dconf-talk-name",
    "finish-args-freedesktop-dbus-system-talk-name",
    "finish-args-freedesktop-dbus-talk-name",
    "external-gitmodule-url-found",
    "toplevel-unnecessary-branch",
    "appstream-metainfo-missing",
    "appid-url-not-reachable",
    "manifest-has-bundled-extension",
    "manifest-file-is-symlink",
    "finish-args-flatpak-appdata-folder-access",
    "finish-args-flatpak-system-folder-access",
    "finish-args-flatpak-user-folder-access",
    "finish-args-host-tmp-access",
    "finish-args-host-var-access",
    "finish-args-only-wayland",
    "finish-args-flatpak-system-talk-name",
    "finish-args-portal-impl-permissionstore-talk-name",
}


def check_duplicates(pairs: list[tuple[str, dict[str, str]]]) -> dict[str, dict[str, str]]:
    d: dict[str, dict[str, str]] = {}
    for key, val in pairs:
        if key in d:
            raise ValueError(f"Duplicate key(s) found: {key}")
        d[key] = val
    return d


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("filenames", nargs="*", help="Input filenames")
    args = parser.parse_args(argv)

    if not args.filenames:
        args.filenames = ["flatpak_builder_lint/staticfiles/exceptions.json"]

    exit_code = 0

    for filename in args.filenames:
        if not os.path.exists(filename) and os.path.isfile(filename):
            print(f"File not found: {filename}")  # noqa: T201
            exit_code = 1
            break
        try:
            with open(filename) as f:
                data = json.load(f, object_pairs_hook=check_duplicates)
        except ValueError as err:
            print(f"{filename}: Failed to decode: {err}")  # noqa: T201
            exit_code = 1
            continue

        found_exceptions = {
            j
            for i in data.values()
            for j in i
            if not j.startswith(
                ("module-", "finish-args-arbitrary-xdg-", "finish-args-unnecessary-xdg-")
            )
        } - {
            "*",
            "appid-filename-mismatch",
            "flathub-json-deprecated-i386-arch-included",
            "toplevel-no-command",
        }

        if not found_exceptions.issubset(KNOWN_EXCEPTIONS):
            print(  # noqa: T201
                "Exception not found in known exceptions list:",
                found_exceptions - KNOWN_EXCEPTIONS,
            )
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
