from . import Check
from collections import defaultdict


class FinishArgsCheck(Check):
    type = "manifest"

    def check(self, manifest):
        finish_args_list = manifest.get("finish-args")
        if not finish_args_list:
            self.errors.append("finish-args-not-defined")
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

        if "xdg-config" in fa["filesystem"]:
            self.errors.append("finish-args-arbitrary-xdg-config-access")

        for fs in fa["filesystem"]:
            for xdg_dir in ["xdg-data", "xdg-config", "xdg-cache"]:
                if fs.startswith(f"{xdg_dir}") and fs.endswith(":create"):
                    self.errors.append("finish-args-unnecessary-xdg-dir-access")

        if "xdg-data" in fa["filesystem"]:
            self.errors.append("finish-args-arbitrary-xdg-data-access")

        for own_name in fa["own-name"]:
            if own_name.startswith("org.kde.StatusNotifierItem"):
                self.errors.append("finish-args-broken-kde-tray-permission")
                break

        if (
            "xdg-config/autostart" in fa["filesystem"]
            or "xdg-config/autostart:create" in fa["filesystem"]
        ):
            self.errors.append("finish-args-arbitrary-autostart-access")
