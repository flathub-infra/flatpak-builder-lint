import argparse
import importlib
import importlib.resources
import json
import pkgutil
import sys

from . import checks, tools

for plugin_info in pkgutil.iter_modules(checks.__path__):
    importlib.import_module(f".{plugin_info.name}", package=checks.__name__)


def run_checks(manifest_filename: str) -> dict:
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

    if appid := manifest.get("id"):
        with importlib.resources.open_text(__package__, "exceptions.json") as f:
            exceptions = json.load(f)

        if app_exceptions := exceptions.get(appid):
            results["errors"] = list(errors - set(app_exceptions))
            results["warnings"] = list(warnings - set(app_exceptions))

    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="A linter for flatpak-builder manifests"
    )
    parser.add_argument("manifest", help="Manifest file to lint", type=str, nargs=1)
    parser.add_argument("--json", help="Output in JSON format", action="store_true")
    args = parser.parse_args()
    exit_code = 0

    if results := run_checks(args.manifest[0]):
        if "errors" in results:
            exit_code = 1

        output = str(results)
        if args.json:
            output = json.dumps(results, indent=4)
        print(output)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
