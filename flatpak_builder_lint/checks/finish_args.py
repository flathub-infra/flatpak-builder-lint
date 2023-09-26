from collections import defaultdict
from typing import Optional, Set

from .. import tools
from . import Check


class FinishArgsCheck(Check):
    def _validate(self, appid: Optional[str], finish_args: dict[str, Set[str]]) -> None:
        if "x11" in finish_args["socket"] and "fallback-x11" in finish_args["socket"]:
            self.warnings.add("finish-args-contains-both-x11-and-fallback")

        if "x11" in finish_args["socket"] and "wayland" in finish_args["socket"]:
            self.warnings.add("finish-args-contains-both-x11-and-wayland")

        if "x11" in finish_args["socket"] or "fallback-x11" in finish_args["socket"]:
            if "ipc" not in finish_args["share"]:
                self.warnings.add("finish-args-x11-without-ipc")

        if (
            "fallback-x11" in finish_args["socket"]
            and "wayland" not in finish_args["socket"]
        ):
            self.errors.add("finish-args-fallback-x11-without-wayland")

        for xdg_dir in ["xdg-data", "xdg-config", "xdg-cache"]:
            if xdg_dir in finish_args["filesystem"]:
                self.errors.add(f"finish-args-arbitrary-{xdg_dir}-access")

            for fs in finish_args["filesystem"]:
                if fs.startswith(f"{xdg_dir}/") and fs.endswith(":create"):
                    self.errors.add(f"finish-args-unnecessary-{xdg_dir}-access")

        if "home" in finish_args["filesystem"] and "host" in finish_args["filesystem"]:
            self.errors.add("finish-args-redundant-home-and-host")

        for own_name in finish_args["own-name"]:
            if own_name.startswith("org.kde.StatusNotifierItem"):
                self.errors.add("finish-args-broken-kde-tray-permission")

            if appid:
                # Values not allowed: appid or appid.*
                # See https://github.com/flathub/flatpak-builder-lint/issues/33
                if own_name == appid or (
                    own_name.startswith(appid) and own_name[len(appid)] == "."
                ):
                    self.errors.add("finish-args-unnecessary-appid-own-name")

        if (
            "xdg-config/autostart" in finish_args["filesystem"]
            or "xdg-config/autostart:create" in finish_args["filesystem"]
        ):
            self.errors.add("finish-args-arbitrary-autostart-access")

        if (
            "system-bus" in finish_args["socket"]
            or "session-bus" in finish_args["socket"]
        ):
            self.errors.add("finish-args-arbitrary-dbus-access")

        if "org.gtk.vfs" in finish_args["talk-name"]:
            # https://github.com/flathub/flathub/issues/2180#issuecomment-811984901
            self.errors.add("finish-args-incorrect-dbus-gvfs")

        if "shm" in finish_args["device"]:
            self.warnings.add("finish-args-deprecated-shm")

        if "all" in finish_args["device"] and len(finish_args["device"]) > 1:
            self.warnings.add("finish-args-redundant-device-all")

        if "org.freedesktop.Flatpak" in finish_args["talk-name"]:
            self.errors.add("finish-args-flatpak-spawn-access")

    def check_manifest(self, manifest: dict) -> None:
        appid = manifest.get("id")
        if isinstance(appid, str):
            is_baseapp = appid.endswith(".BaseApp")
        else:
            is_baseapp = False

        finish_args_list = manifest.get("finish-args")
        build_extension = manifest.get("build-extension")

        if finish_args_list is None and not (build_extension or is_baseapp):
            self.errors.add("finish-args-not-defined")
            return

        if build_extension:
            return

        fa = defaultdict(set)
        if finish_args_list:
            for arg in finish_args_list:
                split = arg.split("=")
                key = split[0].removeprefix("--")
                value = "=".join(split[1:])
                fa[key].add(value)

        self._validate(appid, fa)

    def check_build(self, path: str) -> None:
        metadata = tools.get_metadata(path)
        if metadata.get("type") != "application":
            return

        appid = metadata.get("name")
        if isinstance(appid, str):
            is_baseapp = appid.endswith(".BaseApp")
        else:
            is_baseapp = False

        permissions = metadata.get("permissions", {})
        if not permissions and not is_baseapp:
            self.errors.add("finish-args-not-defined")
            return

        self._validate(appid, permissions)
