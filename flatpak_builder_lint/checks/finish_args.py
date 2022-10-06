from collections import defaultdict

from . import Check


class FinishArgsCheck(Check):
    type = "manifest"

    def check(self, manifest: dict) -> None:
        appid = manifest.get("id")
        if isinstance(appid, str):
            is_baseapp = appid.endswith(".BaseApp")
        else:
            is_baseapp = False

        finish_args_list = manifest.get("finish-args")
        build_extension = manifest.get("build-extension")

        if not finish_args_list and not (build_extension or is_baseapp):
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

        if "x11" in fa["socket"] and "wayland" in fa["socket"]:
            self.warnings.add("finish-args-contains-both-x11-and-wayland")

        if "x11" in fa["socket"] or "fallback-x11" in fa["socket"]:
            if "ipc" not in fa["share"]:
                self.warnings.add("finish-args-x11-without-ipc")

        for xdg_dir in ["xdg-data", "xdg-config", "xdg-cache"]:
            if xdg_dir in fa["filesystem"]:
                self.errors.add(f"finish-args-arbitrary-{xdg_dir}-access")

            for fs in fa["filesystem"]:
                if fs.startswith(f"{xdg_dir}/") and fs.endswith(":create"):
                    self.errors.add(f"finish-args-unnecessary-{xdg_dir}-access")

        if "home" in fa["filesystem"] and "host" in fa["filesystem"]:
            self.errors.add("finish-args-redundant-home-and-host")

        for own_name in fa["own-name"]:
            if own_name.startswith("org.kde.StatusNotifierItem"):
                self.errors.add("finish-args-broken-kde-tray-permission")

            if appid:
                if own_name.startswith(appid):
                    self.errors.add("finish-args-unnecessary-appid-own-name")

        if (
            "xdg-config/autostart" in fa["filesystem"]
            or "xdg-config/autostart:create" in fa["filesystem"]
        ):
            self.errors.add("finish-args-arbitrary-autostart-access")

        if fa["system-bus"] or fa["session-bus"]:
            self.errors.add("finish-args-arbitrary-dbus-access")

        if "org.gtk.vfs" in fa["talk-name"]:
            # https://github.com/flathub/flathub/issues/2180#issuecomment-811984901
            self.errors.add("finish-args-incorrect-dbus-gvfs")

        if "shm" in fa["device"]:
            self.warnings.add("finish-args-deprecated-shm")

        if "all" in fa["device"] and len(fa["device"]) > 1:
            self.errors.add("finish-args-redundant-device-all")

        if "org.freedesktop.Flatpak" in fa["talk-name"]:
            self.errors.add("finish-args-flatpak-spawn-access")
