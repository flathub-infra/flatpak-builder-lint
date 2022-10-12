import argparse
import importlib
import importlib.resources
import json
import pkgutil
import sys

import requests

from . import __version__, checks, staticfiles, tools

for plugin_info in pkgutil.iter_modules(checks.__path__):
    importlib.import_module(f".{plugin_info.name}", package=checks.__name__)


def get_local_exceptions(appid: str) -> set:
    with importlib.resources.open_text(staticfiles, "exceptions.json") as f:
        exceptions = json.load(f)
        ret = exceptions.get(appid)

    if ret:
        return set(ret)

    return set()


def get_remote_exceptions(
    appid: str, api_url: str = "https://flathub.org/api/v2/exceptions"
) -> set:
    try:
        r = requests.get(f"{api_url}/{appid}")
        r.raise_for_status()
        ret = set(r.json())
    except requests.exceptions.RequestException:
        ret = set()

    return ret


def run_checks(manifest_filename: str, enable_exceptions: bool = False) -> dict:
    manifest = tools.show_manifest(manifest_filename)
    for checkclass in checks.ALL:
        check = checkclass()

        if check.type == "manifest":
            check.check(manifest)

    results = {}
    if errors := checks.Check.errors:
        results["errors"] = list(errors)
    if warnings := checks.Check.warnings:
        results["warnings"] = list(warnings)
    if jsonschema := checks.Check.jsonschema:
        results["jsonschema"] = list(jsonschema)

    if enable_exceptions:
        exceptions = None
        if appid := manifest.get("id"):
            exceptions = get_remote_exceptions(appid)
            if not exceptions:
                exceptions = get_local_exceptions(appid)

        if exceptions:
            if "*" in exceptions:
                return {}

            results["errors"] = list(errors - set(exceptions))
            if not results["errors"]:
                results.pop("errors")

            results["warnings"] = list(warnings - set(exceptions))
            if not results["warnings"]:
                results.pop("warnings")

    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="A linter for flatpak-builder manifests"
    )
    parser.add_argument("manifest", help="Manifest file to lint", type=str, nargs=1)
    parser.add_argument("--json", help="Output in JSON format", action="store_true")
    parser.add_argument(
        "--exceptions", help="Skip allowed warnings or errors", action="store_true"
    )
    parser.add_argument(
        "--version", action="version", version=f"flatpak-builder-lint {__version__}"
    )

    args = parser.parse_args()
    exit_code = 0

    if results := run_checks(args.manifest[0], args.exceptions):
        if "errors" in results:
            exit_code = 1

        if args.json:
            output = json.dumps(results, indent=4)
        else:
            # we default to JSON output anyway as it's nicely formatted
            # TODO: make the output more human readable
            output = json.dumps(results, indent=4)

        print(output)

        if args.exceptions and not args.json:
            print()
            print(
                "If you think problems listed above are a false positive, please report it here:"
            )
            print("  https://github.com/flathub/flatpak-builder-lint")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
