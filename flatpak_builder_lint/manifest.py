import errno
import json
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

    base_dir = os.path.dirname(os.path.abspath(filename))
    yaml = YAML(typ="safe")

    yaml_paths = glob(os.path.join(base_dir, "**", "*.yaml"), recursive=True) + glob(
        os.path.join(base_dir, "**", "*.yml"), recursive=True
    )
    json_paths = glob(os.path.join(base_dir, "**", "*.json"), recursive=True)

    for path in sorted(yaml_paths):
        try:
            with open(path) as f:
                yaml.load(f)
        except YAMLError as err:
            rel_path = os.path.relpath(path, base_dir)
            yaml_errors.append(f"{rel_path}: {format_yaml_error(err).strip()}")
    for path in sorted(json_paths):
        try:
            with open(path) as f:
                json.load(f)
        except json.JSONDecodeError as err:
            rel_path = os.path.relpath(path, base_dir)
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
