import argparse
import json
from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("filenames", nargs="*", help="Input filenames")
    args = parser.parse_args(argv)

    if not args.filenames:
        args.filenames = ["flatpak_builder_lint/staticfiles/exceptions.json"]

    exit_code = 0
    json_data = None
    for filename in args.filenames:
        try:
            with open(filename) as f:
                json_data = json.load(f)
        except ValueError as err:
            print(f"{filename}: Failed to decode: {err}")  # noqa: T201
            exit_code = 1

        if json_data is not None:
            try:
                with open(filename, "w") as f:
                    json.dump(json_data, f, sort_keys=True, indent=4)
            except ValueError as err:
                print(f"{filename}: Failed to write: {err}")  # noqa: T201
                exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
