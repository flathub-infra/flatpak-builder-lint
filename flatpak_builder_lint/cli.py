import importlib
import pkgutil
import argparse

from . import checks
from . import tools

for plugin_info in pkgutil.iter_modules(checks.__path__):
    importlib.import_module(f".{plugin_info.name}", package=checks.__name__)


def main():
    parser = argparse.ArgumentParser(description="A linter for flatpak-builder manifests")
    parser.add_argument("manifest", help="Manifest file to lint", type=str, nargs=1)
    args = parser.parse_args()

    manifest = tools.show_manifest(args.manifest)
    for checkclass in checks.ALL:
        check = checkclass()

        if check.type == "manifest":
            check.check(manifest)

if __name__ == "__main__":
    main()
