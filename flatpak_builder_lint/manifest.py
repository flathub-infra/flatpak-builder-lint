import errno
import json
import os
import subprocess
from typing import Any

from . import config, gitutils


# json-glib supports non-standard syntax like // comments. Bail out and
# delegate parsing to flatpak-builder. This also gives us an easy support
# for modules stored in external files.
def show_manifest(filename: str) -> dict[str, Any]:
    if not os.path.exists(filename):
        raise OSError(errno.ENOENT, f"No such manifest file: {filename}")

    ret = subprocess.run(
        ["flatpak-builder", "--show-manifest", filename],
        capture_output=True,
        check=False,
    )

    if ret.returncode != 0:
        raise Exception(ret.stderr.decode("utf-8"))

    manifest = ret.stdout.decode("utf-8")
    manifest_json: dict[str, Any] = json.loads(manifest)
    manifest_json["x-manifest-filename"] = filename

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
