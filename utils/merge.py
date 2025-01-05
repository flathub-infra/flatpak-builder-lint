import argparse
import json
from typing import Any


def merge_duplicates(pairs: list[tuple[str, dict[str, str]]]) -> dict[str, dict[str, str]]:
    d: dict[str, dict[str, str]] = {}
    for key, val in pairs:
        if key in d:
            if isinstance(d[key], dict):
                d[key].update(val)
        else:
            d[key] = val
    return d


def save_file(filename: str, data: dict[str, Any]) -> bool:
    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)
        return True
    except ValueError:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("filenames", nargs="*", help="Input filenames")
    args = parser.parse_args(argv)

    if not args.filenames:
        args.filenames = ["flatpak_builder_lint/staticfiles/exceptions.json"]

    exit_code = 0
    for filename in args.filenames:
        with open(filename) as f:
            merge_data = json.load(f, object_pairs_hook=lambda pairs: merge_duplicates(pairs))
            if merge_data:
                if not save_file(filename, merge_data):
                    exit_code = 1
            else:
                exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
