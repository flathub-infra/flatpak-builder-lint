import errno
import json
import os
from collections import defaultdict

from gi.repository import GLib


def parse_metadata(builddir: str) -> dict:
    if not os.path.exists(builddir):
        raise OSError(errno.ENOENT, f"No such build directory: {builddir}")

    metadata_path = os.path.join(builddir, "metadata")
    if not os.path.exists(metadata_path):
        raise OSError(errno.ENOENT, f"No metadata file in build directory: {builddir}")

    key_file = GLib.KeyFile.new()
    key_file.load_from_file(metadata_path, GLib.KeyFileFlags.NONE)

    metadata: dict = {}

    group = key_file.get_start_group()
    if group is None:
        raise GLib.Error("Start group in metadata not found")

    metadata["type"] = group.lower()
    metadata["name"] = key_file.get_value(group, "name")

    environment: dict = defaultdict(set)
    permissions: dict = defaultdict(set)

    if key_file.has_group("Context"):
        for key in key_file.get_keys("Context")[0]:
            permissions[key] = key_file.get_string_list("Context", key)

    if key_file.has_group("Session Bus Policy"):
        for key in key_file.get_keys("Session Bus Policy")[0]:
            bus_val = key_file.get_value("Session Bus Policy", key)
            permissions[f"{bus_val}-name"].add(key)

    if key_file.has_group("System Bus Policy"):
        for key in key_file.get_keys("System Bus Policy")[0]:
            bus_val = key_file.get_value("System Bus Policy", key)
            permissions[f"system-{bus_val}-name"].add(key)

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

    if key_file.has_group("Environment"):
        for key in key_file.get_keys("Environment")[0]:
            environment[key] = key_file.get_string_list("Environment", key)

    metadata["environment"] = environment

    if key_file.has_group("Extra Data"):
        metadata["extra-data"] = "yes"

    return metadata


def infer_appid(path: str) -> str | None:
    metadata = parse_metadata(path)
    if metadata:
        return metadata.get("name")

    return None


def get_flathub_json(path: str) -> dict[str, str | bool | list[str]]:
    flathub_json_path = f"{path}/files/flathub.json"
    flathub_json: dict = {}

    if os.path.exists(flathub_json_path):
        with open(flathub_json_path) as f:
            flathub_json = json.load(f)

    return flathub_json
