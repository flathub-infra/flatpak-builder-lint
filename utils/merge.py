import argparse
import json
from typing import Any, Sequence


def merge_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    d: dict[str, Any] = {}
    for key, val in pairs:
        if key in d:
            d[key].update(val)
        else:
            d[key] = val
    return d


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("filenames", nargs="*", help="Input filenames")
    args = parser.parse_args(argv)

    if not args.filenames:
        args.filenames = ["flatpak_builder_lint/staticfiles/exceptions.json"]

    exit_code = 0
    merge_data = None
    for filename in args.filenames:
        with open(filename) as f:
            try:
                merge_data = json.load(f, object_pairs_hook=merge_duplicates)
            except ValueError as err:
                print(f"{filename}: Failed to decode: {err}")  # noqa: T201
                exit_code = 1

        if merge_data is not None:
            try:
                with open(filename, "w") as f:
                    json.dump(merge_data, f, indent=4)
            except ValueError as err:
                print(f"{filename}: Failed to write: {err}")  # noqa: T201
                exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
