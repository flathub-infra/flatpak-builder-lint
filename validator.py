import argparse
import json
from typing import Any, Sequence

known_exceptions = {
    "appid-code-hosting-too-few-components",
    "appid-ends-with-lowercase-desktop",
    "appid-uses-code-hosting-domain",
    "appstream-failed-validation",
    "appstream-missing-developer-name",
    "desktop-file-failed-validation",
    "finish-args-arbitrary-autostart-access",
    "finish-args-arbitrary-dbus-access",
    "finish-args-arbitrary-xdg-data-access",
    "finish-args-contains-both-x11-and-wayland",
    "finish-args-flatpak-spawn-access",
    "finish-args-not-defined",
    "finish-args-unnecessary-xdg-cache-access",
    "finish-args-unnecessary-xdg-config-access",
    "finish-args-unnecessary-xdg-data-access",
    "finish-args-wildcard-kde-own-name",
    "flathub-json-modified-publish-delay",
}

def check_duplicates(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    d = {}
    for key, val in pairs:
        if key in d:
            raise ValueError(f"Duplicate key(s) found: {key}")
        else:
            d[key] = val
    return d


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("filenames", nargs="*", help="Input filenames")
    args = parser.parse_args(argv)

    exit_code = 0
    for filename in args.filenames:
        with open(filename, "r") as f:
            try:
                data = json.load(f, object_pairs_hook=check_duplicates)
                found_exceptions = {
                    j for i in data.values() for j in i if not j.startswith("module-")
                } - {
                    "*",
                    "appid-filename-mismatch",
                    "flathub-json-deprecated-i386-arch-included",
                    "toplevel-no-command",
                    "flathub-json-skip-appstream-check",
                    "appstream-missing-appinfo-file",
                }
                if not found_exceptions.issubset(known_exceptions):
                    print("Exception not found in known exceptions list", found_exceptions - known_exceptions)
                    exit_code = 1
            except ValueError as err:
                print(f"{filename}: Failed to decode: {err}")
                exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
