import errno
import json
import os
import subprocess


def is_git_directory(path: str) -> bool:
    res = subprocess.run(
        ["git", "rev-parse"],
        cwd=path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return res.returncode == os.EX_OK


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
    flathub_json_path = os.path.join(manifest_basedir, "flathub.json")
    gitmodules_path = os.path.join(manifest_basedir, ".gitmodules")

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
