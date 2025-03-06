import errno
import json
import os
import subprocess

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


# json-glib supports non-standard syntax like // comments. Bail out and
# delegate parsing to flatpak-builder. This also gives us an easy support
# for modules stored in external files.
def show_manifest(filename: str) -> dict:
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
    manifest_json: dict = json.loads(manifest)
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

    if os.path.exists(gitmodules_path) and is_git_directory(manifest_basedir):
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
