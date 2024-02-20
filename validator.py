import argparse
import json
from typing import Any, Sequence

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
