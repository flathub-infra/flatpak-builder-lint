from collections import defaultdict

from . import Check


class FinishArgsCheck(Check):
    type = "manifest"

    def check(self, manifest):
        appid = manifest.get("id")
        finish_args_list = manifest.get("finish-args")
        build_extension = manifest.get("build-extension")

        if not finish_args_list and not build_extension:
            self.errors.append("finish-args-not-defined")
            return

        if build_extension:
            return

        fa = defaultdict(set)
        for arg in finish_args_list:
            split = arg.split("=")
            key = split[0].removeprefix("--")
            value = "=".join(split[1:])
            fa[key].add(value)

        if "x11" in fa["socket"] and "wayland" in fa["socket"]:
            self.errors.append("finish-args-contains-both-x11-and-wayland")

        if "x11" in fa["socket"] or "fallback-x11" in fa["socket"]:
            if "ipc" not in fa["share"]:
                self.errors.append("finish-args-x11-without-ipc")

        for xdg_dir in ["xdg-data", "xdg-config", "xdg-cache"]:
            if xdg_dir in fa["filesystem"]:
                self.errors.append(f"finish-args-arbitrary-{xdg_dir}-access")

            for fs in fa["filesystem"]:
                if fs.startswith(f"{xdg_dir}/") and fs.endswith(":create"):
                    self.errors.append(f"finish-args-unnecessary-{xdg_dir}-access")

        if "home" in fa["filesystem"] and "host" in fa["filesystem"]:
            self.errors.append("finish-args-redundant-home-and-host")

        for own_name in fa["own-name"]:
            if own_name.startswith("org.kde.StatusNotifierItem"):
                self.errors.append("finish-args-broken-kde-tray-permission")
            elif own_name.startswith(appid):
                self.errors.append("finish-args-unnecessary-appid-own-name")

        if (
            "xdg-config/autostart" in fa["filesystem"]
            or "xdg-config/autostart:create" in fa["filesystem"]
        ):
            self.errors.append("finish-args-arbitrary-autostart-access")

        if fa["system-bus"] or fa["session-bus"]:
            self.errors.append("finish-args-arbitrary-dbus-access")

        if "org.gtk.vfs" in fa["talk-name"]:
            # https://github.com/flathub/flathub/issues/2180#issuecomment-811984901
            self.errors.append("finish-args-incorrect-dbus-gvfs")

        if "shm" in fa["device"]:
            self.warnings.append("finish-args-deprecated-shm")

        if "all" in fa["device"] and len(fa["device"]) > 1:
            self.errors.append("finish-args-redundant-device-all")
