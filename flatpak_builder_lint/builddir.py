import errno
import json
import os
from collections import defaultdict
from configparser import ConfigParser
from typing import Optional


def get_metadata(builddir: str) -> dict:
    if not os.path.exists(builddir):
        raise OSError(errno.ENOENT)

    metadata_path = os.path.join(builddir, "metadata")
    if not os.path.exists(metadata_path):
        raise OSError(errno.ENOENT)

    with open(metadata_path, "r") as f:
        metadata = parse_metadata(f.read())

    return metadata


def parse_metadata(ini: str) -> dict:
    parser = ConfigParser()
    parser.optionxform = str  # type: ignore
    parser.read_string(ini)

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

    if "ExtensionOf" in parser:
        metadata["extension"] = "yes"

    permissions: dict = defaultdict(set)

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

        if "x11" in permissions["socket"] and "fallback-x11" in permissions["socket"]:
            permissions["socket"].remove("x11")

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


def infer_appid(path: str) -> Optional[str]:
    metadata = get_metadata(path)
    if metadata:
        return metadata.get("name")

    return None


def get_flathub_json(path: str) -> Optional[dict]:
    flathub_json_path = f"{path}/files/flathub.json"
    if not os.path.exists(flathub_json_path):
        return None

    with open(flathub_json_path, "r") as f:
        flathub_json: dict = json.load(f)

    return flathub_json
