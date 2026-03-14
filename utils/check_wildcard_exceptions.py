import argparse
import json
import subprocess
import sys
from typing import Any


def get_json_at_ref(ref: str, path: str) -> tuple[dict[str, Any], bool]:
    try:
        out = subprocess.check_output(
            ["git", "show", f"{ref}:{path}"],
            text=True,
        )
        return dict(json.loads(out)), True
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"Failed to read {path} at {ref}: {e}", file=sys.stderr)  # noqa: T201
        return {}, False


def check_wildcard_additions(base: dict[str, Any], head: dict[str, Any]) -> list[str]:
    violations = []
    for appid, head_repos in head.items():
        if any(isinstance(v, str) for v in head_repos.values()):
            continue
        head_wildcard = head_repos.get("*", {})
        if not head_wildcard:
            continue
        base_entry = base.get(appid, {})
        if any(isinstance(v, str) for v in base_entry.values()):
            continue
        base_wildcard = base_entry.get("*", {})
        if not isinstance(base_wildcard, dict):
            continue
        if any(isinstance(v, str) for v in base_wildcard.values()):
            continue
        for exc, reason in head_wildcard.items():
            if exc not in base_wildcard:
                violations.append(
                    f"{appid}/*/{exc}: New exception added under '*' key,"
                    " use a specific repo key instead"
                )
            elif base_wildcard[exc] != reason:
                violations.append(f"{appid}/*/{exc}: Exception reason modified under '*' key")
    return violations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-ref",
        default="origin/master",
        help="Base git ref to compare against (default: origin/master)",
    )
    parser.add_argument(
        "--path",
        default="flatpak_builder_lint/staticfiles/exceptions.json",
        help="Path to exceptions.json",
    )
    args = parser.parse_args()
    base, ret = get_json_at_ref(args.base_ref, args.path)
    if not ret:
        return 1
    with open(args.path, encoding="utf-8") as f:
        try:
            head = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Failed to read {args.path} from ref HEAD: {e}", file=sys.stderr)  # noqa: T201
            return 1
    violations = check_wildcard_additions(base, head)
    if violations:
        print("Additions or modifications under the '*' repo key are not allowed:")  # noqa: T201
        for v in violations:
            print(f"  - {v}")  # noqa: T201
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
