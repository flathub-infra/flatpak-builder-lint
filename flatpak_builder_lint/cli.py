import argparse
import importlib
import pkgutil
import sys

from . import checks, tools

for plugin_info in pkgutil.iter_modules(checks.__path__):
    importlib.import_module(f".{plugin_info.name}", package=checks.__name__)


def main():
    parser = argparse.ArgumentParser(
        description="A linter for flatpak-builder manifests"
    )
    parser.add_argument("manifest", help="Manifest file to lint", type=str, nargs=1)
    args = parser.parse_args()
    exit_code = 0

    manifest = tools.show_manifest(args.manifest[0])
    for checkclass in checks.ALL:
        check = checkclass()

        if check.type == "manifest":
            check.check(manifest)

    if errors := checks.Check.errors:
        exit_code = 1
        print(f"errors: {errors}")

    if warnings := checks.Check.warnings:
        print(f"warnings: {warnings}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
