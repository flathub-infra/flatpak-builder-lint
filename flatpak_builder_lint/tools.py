import errno
import json
import os
import subprocess


# json-glib supports non-standard syntax like // comments. Bail out and
# delegate parsing to flatpak-builder. This also gives us an easy support
# for modules stored in external files.
def show_manifest(filename: str) -> dict:
    if not os.path.exists(filename):
        raise OSError(errno.ENOENT)

    ret = subprocess.run(
        ["flatpak-builder", "--show-manifest", filename], capture_output=True
    )

    if ret.returncode != 0:
        raise Exception(ret.stderr.decode("utf-8"))

    manifest = ret.stdout.decode("utf-8")
    manifest_json = json.loads(manifest)
    manifest_json["x-manifest-filename"] = filename

    manifest_basedir = os.path.dirname(filename)
    flathub_json_path = os.path.join(manifest_basedir, "flathub.json")
    if os.path.exists(flathub_json_path):
        with open(flathub_json_path, "r") as f:
            flathub_json = json.load(f)
            manifest_json["x-flathub"] = flathub_json

    # mypy does not support circular types
    # https://github.com/python/typing/issues/182
    return manifest_json  # type: ignore
