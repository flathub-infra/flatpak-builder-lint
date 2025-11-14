import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from collections.abc import Sequence


def normalize_error_arg(s: str) -> str:
    s = re.sub(r'^[fFrR]{1,2}(?=[\'"])', "", s)

    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        s = s[1:-1]

    return s


def scan_exceptions() -> set[str]:
    pattern = re.compile(r"self\.errors\.add\(\s*(.*?)\s*\)")
    exceptions = set()

    for root, _, files in os.walk("."):
        for filename in files:
            if filename.endswith(".py"):
                path = os.path.join(root, filename)
                try:
                    with open(path, encoding="utf-8") as f:
                        for line in f:
                            m = pattern.search(line)
                            if m:
                                raw = m.group(1).strip()
                                normalized = normalize_error_arg(raw)
                                exceptions.add(normalized)
                except (UnicodeDecodeError, OSError):
                    continue

    return exceptions


KNOWN_EXCEPTIONS = scan_exceptions() | {
    "finish-args-own-name-",
    "finish-args-unnecessary-foo-access",
}

EXP_PREFIX = (
    "module-*-source-*-deprecated",
    "module-*-source-git-*",
    "module-*-checker-tracks-commits",
    "finish-args-arbitrary-*-access",
    "finish-args-unnecessary-*-access",
    "appid-unprefixed-bundled-extension-*",
    "finish-args-own-name-*",
    "finish-args-*-filesystem-access",
)


def match_prefix(exc: str, pattern: str) -> bool:
    return fnmatch.fnmatch(exc, pattern + "*")


def check_prefix_coverage(known: set[str]) -> list[str]:
    missing = []
    for p in EXP_PREFIX:
        if not any(match_prefix(exc, p) for exc in known):
            missing.append(p)

    return missing


def check_duplicates(pairs: list[tuple[str, dict[str, str]]]) -> dict[str, dict[str, str]]:
    d: dict[str, dict[str, str]] = {}
    for key, val in pairs:
        if key in d:
            raise ValueError(f"Duplicate key(s) found: {key}")
        d[key] = val
    return d


def purge_exception(filename: str, exc_name: str) -> bool:
    if not os.path.exists(filename):
        print(f"File not found: {filename}")  # noqa: T201
        return False
    with open(filename) as f:
        data = json.load(f)
    modified = False
    keys_to_delete = []
    for app_id, entries in data.items():
        if exc_name in entries:
            del entries[exc_name]
            modified = True
        if not entries:
            keys_to_delete.append(app_id)
            modified = True
    for k in keys_to_delete:
        del data[k]
    if modified:
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)
        print(f"Purged '{exc_name}' from {filename}")  # noqa: T201
    else:
        print(f"'{exc_name}' not found in {filename}")  # noqa: T201
    return modified


def fetch_valid_appids() -> set[str]:
    appids = {"org.flathub.exceptions", "org.flathub.exceptions_wildcard"}

    def collect_from_flatpak(remote: str) -> None:
        try:
            out = subprocess.check_output(
                ["flatpak", "remote-ls", "--arch=*", "--columns=application", remote],
                text=True,
            )
        except subprocess.CalledProcessError:
            return

        for line in out.splitlines():
            line_s = line.strip()
            if not line_s or line_s == "Application ID":
                continue
            appids.add(line_s)

    collect_from_flatpak("flathub")
    collect_from_flatpak("flathub-beta")

    try:
        out = subprocess.check_output(
            [
                "gh",
                "pr",
                "list",
                "-L",
                "3000",
                "--repo",
                "flathub/flathub",
                "--state",
                "open",
                "--base",
                "new-pr",
                "--search",
                "in:title Add",
                "--json",
                "title",
            ],
            text=True,
        )
        prs = json.loads(out)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        prs = []

    pat = re.compile(r"Add\s+([A-Za-z0-9._-]+)")

    for pr in prs:
        title = pr.get("title", "")
        m = pat.search(title)
        if m:
            appids.add(m.group(1))

    return appids


def purge_unknown_ids(filename: str, valid_appids: set[str]) -> bool:
    if not os.path.exists(filename):
        print(f"File not found: {filename}")  # noqa: T201
        return False
    with open(filename) as f:
        data = json.load(f)
    modified = False
    keys_to_delete = [app_id for app_id in data if app_id not in valid_appids]
    for app_id in keys_to_delete:
        del data[app_id]
        modified = True
        print(f"Purged unknown app-ID '{app_id}' from {filename}")  # noqa: T201
    if modified:
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)
    return modified


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("filenames", nargs="*", help="Input filenames")
    parser.add_argument("--purge", metavar="EXCEPTION", help="Remove an exception from the file")
    parser.add_argument(
        "--purge-unknown-ids",
        action="store_true",
        help="Remove app IDs in exceptions file that are not present in Flathub's list",
    )
    args = parser.parse_args(argv)

    if not args.filenames:
        args.filenames = ["flatpak_builder_lint/staticfiles/exceptions.json"]

    if args.purge:
        exc = args.purge
        modified_any = False
        for filename in args.filenames:
            if purge_exception(filename, exc):
                modified_any = True
        return 0 if modified_any else 1

    if args.purge_unknown_ids:
        valid_appids = fetch_valid_appids()
        if not valid_appids:
            print("No valid app-IDs fetched; aborting purge-unknown-ids.", file=sys.stderr)  # noqa: T201
            return 1
        modified_any = False
        for filename in args.filenames:
            if purge_unknown_ids(filename, valid_appids):
                modified_any = True
        return 0 if modified_any else 1

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
            j for i in data.values() for j in i if not any(match_prefix(j, p) for p in EXP_PREFIX)
        } - {
            "*",
            "appid-filename-mismatch",
            "flathub-json-deprecated-i386-arch-included",
            "toplevel-no-command",
        }

        prefix_match = check_prefix_coverage(KNOWN_EXCEPTIONS)
        if prefix_match:
            print(f"Exception prefix does not match any known exceptions: {prefix_match}")  # noqa: T201
            exit_code = 1

        if not found_exceptions.issubset(KNOWN_EXCEPTIONS):
            print(  # noqa: T201
                "Exception not found in known exceptions list:",
                found_exceptions - KNOWN_EXCEPTIONS,
            )
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
