import argparse
import json
import os


def read_appid(id_input: str) -> set[str]:
    app_ids = set()
    if os.path.exists(id_input) and os.path.isfile(id_input):
        try:
            with open(id_input) as f:
                for line in f:
                    app_ids.add(line.strip())
        except FileNotFoundError:
            pass
    else:
        app_ids.add(id_input)
    return app_ids


def generate_exceptions(
    app_ids: set[str], exceptions: set[str], reason: str
) -> dict[str, dict[str, str]]:
    reason = reason if reason else "Predates the linter rule"
    return {app: dict.fromkeys(exceptions, reason) for app in app_ids}


def main(appid: str, exceptions: set[str], reason: str) -> None:
    reason = reason if reason else "Predates the linter rule"

    app_ids = read_appid(appid)

    if not exceptions:
        raise ValueError("No exceptions provided")

    data = generate_exceptions(app_ids, exceptions, reason)
    print(json.dumps(data, sort_keys=True, indent=4))  # noqa: T201


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--appid",
        type=str,
        required=True,
        help="Input filename with 1 appid per line or a single appid",
    )
    parser.add_argument(
        "--exception",
        action="extend",
        nargs="*",
        type=str,
        required=True,
        help="Input error code to create exception. Can be used multiple times",
    )
    parser.add_argument(
        "--reason",
        type=str,
        help="Input optional reason string",
    )
    args = parser.parse_args()
    main(args.appid, set(args.exception), args.reason)
