import argparse
import importlib
import importlib.resources
import json
import logging
import os
import pkgutil
import sys
import textwrap
from types import MappingProxyType
from typing import Any

import sentry_sdk

from . import (
    __version__,
    appstream,
    builddir,
    checks,
    config,
    domainutils,
    exceptions_janitor,
    manifest,
    ostree,
    staticfiles,
)

if sentry_dsn := os.getenv("SENTRY_DSN"):
    sentry_sdk.init(sentry_dsn)

for plugin_info in pkgutil.iter_modules(checks.__path__):
    importlib.import_module(f".{plugin_info.name}", package=checks.__name__)


def setup_logging(debug: bool = False) -> None:
    if debug:
        logging.basicConfig(level=logging.CRITICAL + 1, format="%(levelname)s: %(message)s")
        logging.getLogger("flatpak_builder_lint").setLevel(logging.DEBUG)
    else:
        logging.disable(logging.CRITICAL)


def _filter(info: set[str], excepts: set[str]) -> list[str]:
    final = set()
    for i in info:
        count = False
        for j in excepts:
            if i is not None and i.startswith(j):
                count = True
                break
        if not count:
            final.add(i)
    return list(final)


def get_local_exceptions(appid: str) -> set[str]:
    with importlib.resources.open_text(staticfiles, "exceptions.json") as f:
        exceptions = json.load(f)
        ret = exceptions.get(appid, [])

    if ret:
        return set(ret)

    return set()


def get_user_exceptions(file: str, appid: str) -> set[str]:
    if os.path.exists(file) and os.path.isfile(file):
        with open(file, encoding="utf-8") as f:
            exceptions = json.load(f)
            return set(exceptions.get(appid, []))
    return set()


def print_gh_annotations(results: dict[str, str | list[str]], artifact_type: str) -> None:
    if not results:
        return

    info: dict[str, str] = {
        k.strip(): v.strip()
        for entry in results.get("info", [])
        if ": " in entry
        for k, v in [entry.split(": ", 1)]
    }

    for level, prefix in [("errors", "::error::"), ("warnings", "::warning::")]:
        msg_type = level[:-1]
        for msg in results.get(level, []):
            detail = f"Details: {info.get(msg)}" if msg in info else ""
            print(f"{prefix}{msg!r} {msg_type} found in linter {artifact_type} check. {detail}")  # noqa: T201

    for line in results.get("appstream", []):
        print(f"::error::Appstream: {line.strip()!r}")  # noqa: T201

    if help_msg := results.get("message"):
        print(f"::notice::💡 {help_msg}")  # noqa: T201


def run_checks(
    kind: str,
    path: str,
    enable_exceptions: bool = False,
    appid: str | None = None,
    user_exceptions_path: str | None = None,
    enable_janitor_exceptions: bool = False,
) -> dict[str, str | list[str]]:
    stale_exceptions: set[str] | None = None

    match kind:
        case "manifest":
            check_method_name = "check_manifest"
            infer_appid_func = manifest.infer_appid
            check_method_arg: str | MappingProxyType[str, Any] = manifest.show_manifest(path)
        case "builddir":
            check_method_name = "check_build"
            infer_appid_func = builddir.infer_appid
            check_method_arg = path
        case "repo":
            check_method_name = "check_repo"
            infer_appid_func = ostree.infer_appid
            check_method_arg = path
        case _:
            raise ValueError(f"Unknown kind: {kind}")

    for checkclass in checks.ALL:
        check = checkclass()

        if (check_method := getattr(check, check_method_name, None)) and callable(check_method):
            check_method(check_method_arg)

    results: dict[str, str | list[str]] = {}
    if errors := checks.Check.errors:
        results["errors"] = list(errors)
    if warnings := checks.Check.warnings:
        results["warnings"] = list(warnings)
    if jsonschema := checks.Check.jsonschema:
        results["jsonschema"] = list(jsonschema)
    if appstream := checks.Check.appstream:
        results["appstream"] = list(appstream)
    if desktopfile := checks.Check.desktopfile:
        results["desktopfile"] = list(desktopfile)
    if info := checks.Check.info:
        results["info"] = list(info)

    if enable_exceptions:
        exceptions = None

        appid = appid[0] if appid else infer_appid_func(path)

        if appid:
            if user_exceptions_path:
                exceptions = get_user_exceptions(user_exceptions_path, appid)
            else:
                exceptions = domainutils.get_remote_exceptions(appid)

            if not exceptions:
                exceptions = get_local_exceptions(appid)

        if exceptions:
            if (
                enable_janitor_exceptions
                and appid
                and config.is_flathub_build_pipeline()
                and (stale_raw := exceptions_janitor.get_stale_exceptions(errors, exceptions))
            ):
                ignore_stale_exceptions: set[str] = {"appid-url-not-reachable"}
                stale_exceptions = stale_raw - ignore_stale_exceptions
                if stale_exceptions:
                    exceptions_janitor.report_stale_exceptions(appid, stale_exceptions)

            if "*" in exceptions:
                return {}

            results["errors"] = list(errors - set(exceptions))
            if not results["errors"]:
                results.pop("errors")

            warnings_lst = list(warnings - set(exceptions))
            if stale_exceptions:
                warnings_lst.append("stale-exceptions-found")
            results["warnings"] = warnings_lst
            if not results["warnings"]:
                results.pop("warnings")

            if "appstream-failed-validation" in set(exceptions):
                results.pop("appstream", None)

            if "desktop-file-failed-validation" in set(exceptions):
                results.pop("desktopfile", None)

            info_lst = _filter(set(info), set(exceptions))
            if stale_exceptions:
                info_lst.append(f"stale-exceptions-found: {', '.join(sorted(stale_exceptions))}")
            results["info"] = info_lst
            if not results["info"]:
                results.pop("info")

    help_text = "See https://docs.flathub.org/linter for details and exceptions"

    if any(x in results for x in ("errors", "warnings", "info")):
        results["message"] = help_text

    return results


def main() -> int:
    description = textwrap.dedent("""\
        flatpak-builder-lint

        A linter for Flatpak manifests and build artifacts primarily
        developed for Flathub
    """)
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawTextHelpFormatter,
        usage=argparse.SUPPRESS,
        add_help=False,
        epilog=f"Please report any issues at https://github.com/{config.LINTER_FULL_REPO}",
    )
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        help="Show this help message and exit",
    )
    parser.add_argument(
        "--version",
        action="version",
        help="Show the version number and exit",
        version=f"flatpak-builder-lint {__version__}",
    )
    parser.add_argument(
        "--exceptions",
        help="Skip errors added to exceptions. Exceptions must be submitted to Flathub",
        action="store_true",
    )
    parser.add_argument(
        "--user-exceptions",
        help="Path to a JSON file with exceptions",
        type=str,
        metavar="",
    )
    parser.add_argument(
        "--appid", help="Override the app ID with this app ID", type=str, metavar="", nargs=1
    )
    parser.add_argument(
        "--cwd",
        help="Override the path parameter with the current working directory",
        action="store_true",
    )
    parser.add_argument(
        "--ref",
        help="Override the primary ref detection with this ref",
        type=str,
        action="append",
        default=[],
        metavar="",
    )
    parser.add_argument(
        "type",
        choices=["appstream", "manifest", "builddir", "repo"],
        help=textwrap.dedent("""\
            Type of artifact to lint

              appstream expects a MetaInfo file
              manifest  expects a flatpak-builder manifest
              builddir  expects a flatpak-builder build directory
              repo      expects an OSTree repo exported by flatpak-builder\n\n"""),
    )
    parser.add_argument(
        "path",
        help="Path to the artifact",
        type=str,
        nargs=1,
        metavar="PATH",
    )
    parser.add_argument(
        "--gha-format",
        help="Use GitHub Actions annotations in CI",
        action="store_true",
    )
    parser.add_argument(
        "--janitor-exceptions",
        help="Enable reporting of stale exceptions to linter repository",
        action="store_true",
    )
    parser.add_argument(
        "--debug",
        help="Enable debug logging",
        action="store_true",
    )

    args = parser.parse_args()
    setup_logging(args.debug)

    logger = logging.getLogger(__name__)
    logger.debug("flatpak-builder-lint version: %s", __version__)

    exit_code = 0

    path = os.getcwd() if args.cwd else args.path[0]

    if args.ref:
        checks.Check.repo_primary_refs = set(args.ref)

    if args.type != "appstream":
        if results := run_checks(
            args.type,
            path,
            args.exceptions,
            args.appid,
            args.user_exceptions,
            args.janitor_exceptions,
        ):
            if "errors" in results:
                exit_code = 1

            if os.environ.get("GITHUB_ACTIONS") == "true" and args.gha_format:
                print_gh_annotations(results, args.type)
            else:
                print(json.dumps(results, indent=4))  # noqa: T201
    else:
        appstream_results = appstream.validate(path, "--explain")
        print(appstream_results["stdout"])  # noqa: T201
        print(appstream_results["stderr"])  # noqa: T201
        exit_code = appstream_results["returncode"]

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
