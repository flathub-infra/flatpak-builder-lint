import errno
import json
import os
import subprocess
from collections import defaultdict
from configparser import ConfigParser
from typing import Optional


# json-glib supports non-standard syntax like // comments. Bail out and
# delegate parsing to flatpak-builder. This also gives us an easy support
# for modules stored in external files.
def show_manifest(filename: str) -> dict:
    if not os.path.exists(filename):
        raise OSError(errno.ENOENT)

    ret = subprocess.run(
        ["flatpak-builder", "--show-manifest", filename],
        capture_output=True,
    )

    if ret.returncode != 0:
        raise Exception(ret.stderr.decode("utf-8"))

    manifest = ret.stdout.decode("utf-8")
    manifest_json = json.loads(manifest)
    manifest_json["x-manifest-filename"] = filename

    manifest_basedir = os.path.dirname(filename)
    flathub_json_path = os.path.join(manifest_basedir, "flathub.json")
    if os.path.exists(flathub_json_path):
        with open(flathub_json_path) as f:
            flathub_json = json.load(f)
            manifest_json["x-flathub"] = flathub_json

    # mypy does not support circular types
    # https://github.com/python/typing/issues/182
    return manifest_json  # type: ignore


def infer_appid_from_manifest(filename: str) -> Optional[str]:
    manifest = show_manifest(filename)
    return manifest.get("id")


def get_metadata(builddir: str) -> dict:
    if not os.path.exists(builddir):
        raise OSError(errno.ENOENT)

    metadata_path = os.path.join(builddir, "metadata")
    if not os.path.exists(metadata_path):
        raise OSError(errno.ENOENT)

    parser = ConfigParser()
    parser.optionxform = str
    parser.read(metadata_path)

    if "Application" in parser:
        metadata: dict = dict(parser["Application"])
        metadata["type"] = "application"
    elif "Runtime" in parser:
        metadata = dict(parser["Runtime"])
        metadata["type"] = "runtime"
    else:
        return {}

    if "tags" in metadata:
        tags = [x for x in metadata["tags"].split(";") if x]
        metadata["tags"] = tags

    permissions = defaultdict(set)

    if "Context" in parser:
        for key in parser["Context"]:
            permissions[key] = [x for x in parser["Context"][key].split(";") if x]
        parser.remove_section("Context")

    if "Session Bus Policy" in parser:
        bus_metadata = parser["Session Bus Policy"]

        for busname in bus_metadata:
            bus_permission = bus_metadata[busname]
            permissions[f"{bus_permission}-name"].add(busname)

    if "System Bus Policy" in parser:
        bus_metadata = parser["System Bus Policy"]

        for busname in bus_metadata:
            bus_permission = bus_metadata[busname]
            permissions[f"system-{bus_permission}-name"].add(busname)

    if "shared" in permissions:
        permissions["share"] = permissions.pop("shared")

    if "filesystems" in permissions:
        permissions["filesystem"] = permissions.pop("filesystems")

    if "sockets" in permissions:
        permissions["socket"] = permissions.pop("sockets")

    if "devices" in permissions:
        permissions["device"] = permissions.pop("devices")

    metadata["permissions"] = permissions

    extensions = {}
    for section in parser:
        if section.startswith("Extension "):
            extname = section[10:]
            extensions[extname] = dict(parser[section])

    if extensions:
        metadata["extensions"] = extensions

    if "Build" in parser:
        metadata["built-extensions"] = [
            x for x in parser.get("Build", "built-extensions").split(";") if x
        ]

    if "Extra Data" in parser:
        metadata["extra-data"] = dict(parser["Extra Data"])

    return metadata


def infer_appid_from_metadata(builddir: str) -> Optional[str]:
    metadata = get_metadata(builddir)
    if metadata:
        return metadata.get("name")

    return None
