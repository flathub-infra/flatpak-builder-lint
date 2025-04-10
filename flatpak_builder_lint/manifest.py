import errno
import json
import os
import re
import subprocess
from typing import Any

from . import config


def is_git_directory(path: str) -> bool:
    if not os.path.exists(path):
        return False
    return (
        subprocess.run(
            ["git", "rev-parse"],
            cwd=path,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def get_git_toplevel(path: str) -> str | None:
    if not is_git_directory(path):
        return None

    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=path,
        capture_output=True,
        text=True,
        check=False,
    )

    return result.stdout.strip() if result.returncode == 0 else None


def get_github_repo_namespace(path: str) -> str | None:
    namespace = None

    if not is_git_directory(path):
        return None

    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=path,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        return None

    remote_url = result.stdout.strip()

    https_pattern = r"https://github\.com/([^/]+/[^/.]+)"
    ssh_pattern = r"git@github\.com:([^/]+/[^.]+)"

    https_match = re.search(https_pattern, remote_url)
    ssh_match = re.search(ssh_pattern, remote_url)

    if https_match and "/" in https_match.group(1):
        namespace = https_match.group(1).split("/")[0]
    elif ssh_match and "/" in ssh_match.group(1):
        namespace = ssh_match.group(1).split("/")[0]

    return namespace


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
    git_toplevel = get_git_toplevel(manifest_basedir)
    flathub_json_path = os.path.join(manifest_basedir, config.FLATHUB_JSON_FILE)
    gitmodules_path = os.path.join(manifest_basedir, ".gitmodules")

    if git_toplevel is not None:
        gitmodules_path = os.path.join(git_toplevel, ".gitmodules")

    if os.path.exists(flathub_json_path):
        with open(flathub_json_path) as f:
            flathub_json = json.load(f)
            manifest_json["x-flathub"] = flathub_json

    github_ns = get_github_repo_namespace(manifest_basedir)

    if os.path.exists(gitmodules_path) and github_ns in ("flathub", "flathub-infra"):
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
