import errno
import json
import logging
import os
import re
import subprocess
from functools import cache
from glob import glob
from types import MappingProxyType
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError

from . import config, gitutils

logger = logging.getLogger(__name__)


def load_json_glib_manifest(path: str) -> dict[str, Any] | None:
    if not os.path.isfile(path):
        logger.debug("Failed to find manifest: %s", path)
        return None

    manifest: dict[str, Any] | None

    def _strip_comments(text: str) -> str:
        result = []
        i = 0
        n = len(text)
        while i < n:
            if text[i] == '"':
                result.append(text[i])
                i += 1
                while i < n:
                    ch = text[i]
                    result.append(ch)
                    if ch == "\\" and i + 1 < n:
                        i += 1
                        result.append(text[i])
                    elif ch == '"':
                        break
                    i += 1
                i += 1
            elif text[i : i + 2] == "/*":
                i += 2
                while i < n and text[i : i + 2] != "*/":
                    i += 1
                i += 2
            else:
                result.append(text[i])
                i += 1
        return "".join(result)

    with open(path) as f:
        try:
            manifest = json.loads(_strip_comments(f.read()))
        except json.JSONDecodeError as err:
            logger.debug("Failed to parse manifest %s: %s", path, err)
            return None

    return manifest


def collect_sub_manifests(filename: str) -> list[str] | None:
    yaml = YAML(typ="safe")
    visited: set[str] = set()
    result: list[str] = []
    parse_failed = False

    def _load(path: str) -> dict[str, Any] | None:
        manifest: dict[str, Any] | None
        if path.endswith((".yaml", ".yml")):
            try:
                with open(path) as f:
                    manifest = yaml.load(f)
            except YAMLError as err:
                logger.debug("Failed to parse manifest %s: %s", path, err)
                return None
        else:
            manifest = load_json_glib_manifest(path)

        return manifest

    def _collect(manifest_path: str) -> None:
        nonlocal parse_failed
        abs_path = os.path.abspath(manifest_path)
        if abs_path in visited:
            return
        visited.add(abs_path)
        data = _load(abs_path)
        if data is None:
            if abs_path == os.path.abspath(filename):
                parse_failed = True
            return
        if not isinstance(data, dict):
            logger.debug(
                "Not collecting sub-manifests from the non-dict manifest %s", manifest_path
            )
            return
        base_dir = os.path.dirname(abs_path)
        _collect_modules(data.get("modules", []), base_dir)

    def _collect_modules(modules: list[str], base_dir: str) -> None:
        for module in modules:
            if isinstance(module, str):
                sub_abs = os.path.abspath(os.path.join(base_dir, module))
                if os.path.isfile(sub_abs):
                    result.append(sub_abs)
                    _collect(sub_abs)
            elif isinstance(module, dict):
                _collect_modules(module.get("modules", []), base_dir)

    _collect(filename)
    return None if parse_failed else list(set(result))


def format_yaml_error(e: YAMLError) -> str:
    err_type = f"{type(e).__module__}.{type(e).__name__}"
    msg = " ".join(
        line.strip()
        for line in str(e).splitlines()
        if not line.strip().startswith("To suppress this check")
        and not line.strip().startswith("https://yaml.dev/")
    )
    return f"{err_type} {msg}"


def get_key_lineno(manifest_path: str, key: str) -> int | None:
    if not os.path.isfile(manifest_path):
        return None

    if manifest_path.lower().endswith(".json"):
        try:
            with open(manifest_path, encoding="utf-8") as f:
                for i, line in enumerate(f, start=1):
                    if f'"{key}"' in line or f"'{key}'" in line:
                        return i
        except (OSError, json.JSONDecodeError):
            return None

    elif manifest_path.lower().endswith((".yaml", ".yml")):
        yaml = YAML()
        yaml.preserve_quotes = True
        try:
            with open(manifest_path, encoding="utf-8") as f:
                data = yaml.load(f)
        except (OSError, YAMLError):
            return None

        if isinstance(data, CommentedMap) and key in data:
            node = data.ca.items.get(key)
            if node and node[0] and hasattr(node[0], "start_mark"):
                return int(node[0].start_mark.line + 1)

        try:
            with open(manifest_path, encoding="utf-8") as f:
                for i, line in enumerate(f, start=1):
                    if key in line:
                        return i
        except OSError:
            return None

    return None


def validate_manifest_files(filename: str) -> tuple[list[str], list[str]]:
    yaml_errors: list[str] = []
    json_errors: list[str] = []
    yaml = YAML(typ="safe")
    base_dir = os.path.dirname(os.path.abspath(filename))
    sub_manifests = collect_sub_manifests(filename)

    if sub_manifests is None:
        logger.debug("Failed to collect sub-manifests by parsing, falling back to a recursive scan")
        sub_manifests = (
            glob(os.path.join(base_dir, "**", "*.yaml"), recursive=True)
            + glob(os.path.join(base_dir, "**", "*.yml"), recursive=True)
            + glob(os.path.join(base_dir, "**", "*.json"), recursive=True)
        )

    manifests_to_validate = {*sub_manifests, os.path.abspath(filename)}

    for manifest_path in sorted(manifests_to_validate):
        if os.path.exists(manifest_path):
            try:
                if manifest_path.endswith((".yaml", ".yml")):
                    with open(manifest_path) as f:
                        yaml.load(f)
                else:
                    with open(manifest_path) as f:
                        json.loads(f.read())
            except YAMLError as err:
                rel_path = os.path.relpath(manifest_path, base_dir)
                yaml_errors.append(f"{rel_path}: {format_yaml_error(err).strip()}")
            except json.JSONDecodeError as err:
                rel_path = os.path.relpath(manifest_path, base_dir)
                json_errors.append(f"{rel_path}: {err.msg} (line {err.lineno}, column {err.colno})")

    return yaml_errors, json_errors


# json-glib supports non-standard syntax like // comments. Bail out and
# delegate parsing to flatpak-builder. This also gives us an easy support
# for modules stored in external files.
@cache
def show_manifest(filename: str) -> MappingProxyType[str, Any]:
    if not os.path.exists(filename):
        raise OSError(errno.ENOENT, f"No such manifest file: {filename}")

    yaml_errors, json_errors = validate_manifest_files(filename)

    ret = subprocess.run(
        ["flatpak-builder", "--show-manifest", filename],
        capture_output=True,
        check=False,
        env={
            **os.environ,
            "LANGUAGE": "C",
            "LC_ALL": "C",
            "G_MESSAGES_PREFIXED": "all",
        },
    )

    stderr_s = ret.stderr.decode("utf-8")
    stdout_s = ret.stdout.decode("utf-8")

    unknown_pat = re.compile(
        r"^\*\* \(flatpak-builder:\d+\): WARNING \*\*: "
        r"[\d:.]+: Unknown property (\S+) for type (\S+)"
    )

    json_warning_pat = re.compile(r"^\(flatpak-builder:\d+\): Json-WARNING \*\*: " r"[\d:.]+: (.+)")

    unknown_properties: list[dict[str, str]] = []
    json_warnings: list[str] = []

    if stderr_s:
        for line in stderr_s.splitlines():
            if m := unknown_pat.match(line):
                type_name = m.group(2).strip()
                context = (
                    "source"
                    if type_name == "BuilderSource"
                    else "source-" + type_name[13:].lower()
                    if type_name.startswith("BuilderSource")
                    else type_name[7:].lower()
                    if type_name.startswith("Builder")
                    else type_name
                )
                unknown_properties.append({"property": m.group(1).strip(), "context": context})
            elif m := json_warning_pat.match(line):
                json_warnings.append(m.group(1).strip())

    if ret.returncode != 0:
        raise Exception(stderr_s)

    manifest = stdout_s
    manifest_json: dict[str, Any] = json.loads(manifest)
    manifest_json["x-manifest-filename"] = filename

    if unknown_properties:
        manifest_json["x-manifest-unknown-properties"] = list(
            {(p["property"], p["context"]): p for p in unknown_properties}.values()
        )

    if json_warnings:
        manifest_json["x-manifest-json-warnings"] = json_warnings

    if yaml_errors:
        manifest_json["x-manifest-yaml-failed"] = yaml_errors

    if json_errors:
        manifest_json["x-manifest-json-failed"] = json_errors

    manifest_basedir = os.path.dirname(os.path.abspath(filename))
    git_toplevel = gitutils.get_git_toplevel(manifest_basedir)
    flathub_json_path = os.path.join(manifest_basedir, config.FLATHUB_JSON_FILE)
    gitmodules_path = os.path.join(manifest_basedir, ".gitmodules")

    if git_toplevel is not None:
        gitmodules_path = os.path.join(git_toplevel, ".gitmodules")

    if os.path.exists(flathub_json_path):
        with open(flathub_json_path) as f:
            flathub_json = json.load(f)
            manifest_json["x-flathub"] = flathub_json

    github_ns = gitutils.get_github_repo_namespace(manifest_basedir)

    if github_ns in ("flathub", "flathub-infra"):
        if gitutils.get_repo_tree_size(manifest_basedir) > (25 * 1024 * 1024):
            manifest_json["x-manifest-dir-large"] = True

        if os.path.exists(gitmodules_path):
            with open(gitmodules_path) as f:
                manifest_json["x-gitmodules"] = [
                    line.split("=", 1)[1].strip()
                    for line in f.readlines()
                    if line.strip().startswith("url")
                    and not line.split("=", 1)[1].strip().startswith(("./", "../"))
                ]

    return MappingProxyType(manifest_json)


def infer_appid(path: str) -> str | None:
    manifest = show_manifest(path)
    return manifest.get("id")
