import errno
import json
import os
import re
import subprocess
from typing import Any

from ruamel.yaml import YAML
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


# json-glib supports non-standard syntax like // comments. Bail out and
# delegate parsing to flatpak-builder. This also gives us an easy support
# for modules stored in external files.
def show_manifest(filename: str) -> dict[str, Any]:
    if not os.path.exists(filename):
        raise OSError(errno.ENOENT, f"No such manifest file: {filename}")

    yaml_err: str | None = None
    if os.path.basename(filename).lower().endswith((".yaml", ".yml")):
        try:
            with open(filename) as f:
                YAML(typ="safe").load(f)
        except YAMLError as err:
            yaml_err = format_yaml_error(err).strip()

    ret = subprocess.run(
        ["flatpak-builder", "--show-manifest", filename],
        capture_output=True,
        check=False,
        env={**os.environ, "G_MESSAGES_PREFIXED": "all"},
    )

    stderr_s = ret.stderr.decode("utf-8")
    stdout_s = ret.stdout.decode("utf-8")

    pat = re.compile(
        r"^\*\* \(flatpak-builder:\d+\): WARNING \*\*: " r"[\d:.]+: Unknown property (\S+) for type"
    )
    unknown_properties: list[str] = []
    if stderr_s:
        unknown_properties = [m.group(1) for line in stderr_s.split("\n") if (m := pat.match(line))]

    if ret.returncode != 0:
        raise Exception(stderr_s)

    manifest = stdout_s
    manifest_json: dict[str, Any] = json.loads(manifest)
    manifest_json["x-manifest-filename"] = filename

    if unknown_properties:
        manifest_json["x-manifest-unknown-properties"] = unknown_properties

    if yaml_err:
        manifest_json["x-manifest-yaml-failed"] = yaml_err

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

    return manifest_json


def infer_appid(path: str) -> str | None:
    manifest = show_manifest(path)
    return manifest.get("id")
