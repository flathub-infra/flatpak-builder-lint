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
    appid: str, api_url: str = "http://localhost:8000/exceptions"
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
            results["errors"] = list(errors - set(exceptions))
            results["warnings"] = list(warnings - set(exceptions))

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
            output = str(results)

        print(output)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
