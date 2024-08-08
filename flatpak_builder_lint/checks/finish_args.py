import re
import tempfile
from collections import defaultdict
from typing import Optional, Set

from .. import builddir, ostree
from . import Check


class FinishArgsCheck(Check):
    def _validate(self, appid: Optional[str], finish_args: dict[str, Set[str]]) -> None:
        if "x11" in finish_args["socket"] and "fallback-x11" in finish_args["socket"]:
            self.errors.add("finish-args-contains-both-x11-and-fallback")

        if "x11" in finish_args["socket"] and "wayland" in finish_args["socket"]:
            self.errors.add("finish-args-contains-both-x11-and-wayland")

        if "x11" in finish_args["socket"] or "fallback-x11" in finish_args["socket"]:
            if "ipc" not in finish_args["share"]:
                self.errors.add("finish-args-x11-without-ipc")

        if (
            "fallback-x11" in finish_args["socket"]
            and "wayland" not in finish_args["socket"]
        ):
            self.errors.add("finish-args-fallback-x11-without-wayland")
            self.info.add(
                "finish-args-fallback-x11-without-wayland: finish-args has fallback-x11"
                + " but no wayland socket"
            )

        if "wayland" in finish_args["socket"] and (
            "x11" not in finish_args["socket"]
            and "fallback-x11" not in finish_args["socket"]
        ):
            self.errors.add("finish-args-only-wayland")
            self.info.add(
                "finish-args-only-wayland: finish-args has only wayland socket"
                + " but no x11 or fallback-x11 socket"
            )

        for socket in finish_args["socket"]:
            if socket.startswith("!"):
                soc = socket.removeprefix("!")
                self.errors.add(f"finish-args-has-nosocket-{soc}")

        for share in finish_args["share"]:
            if share.startswith("!"):
                shr = share.removeprefix("!")
                self.errors.add(f"finish-args-has-unshare-{shr}")

        for dev in finish_args["device"]:
            if dev.startswith("!"):
                dv = dev.removeprefix("!")
                self.errors.add(f"finish-args-has-nodevice-{dv}")

        modes = (":ro", ":rw", ":create")
        xdgdirs = ("xdg-data", "xdg-config", "xdg-cache")
        for xdg_dir in xdgdirs:
            regexp_arbitrary = f"^{xdg_dir}(:(create|rw|ro)?)?$"
            regexp_unnecessary = f"^{xdg_dir}(\\/.*)?(:(create|rw|ro)?)?$"
            for fs in finish_args["filesystem"]:
                # This is inherited by apps from the KDE runtime
                if fs == "xdg-config/kdeglobals:ro":
                    continue

                mode_suffix = "rw"
                if fs.startswith(xdgdirs) and fs.endswith(modes):
                    mode_src = [i for i in modes if fs.endswith(i)][0]
                    mode_suffix = mode_src.split(":", 1)[1]

                if re.match(regexp_arbitrary, fs):
                    self.errors.add(
                        f"finish-args-arbitrary-{xdg_dir}-{mode_suffix}-access"
                    )
                elif re.match(regexp_unnecessary, fs):
                    subdir = fs.split("/")[1]
                    if subdir.endswith(modes):
                        subdir = subdir.split(":", 1)[0]
                    self.errors.add(
                        f"finish-args-unnecessary-{xdg_dir}-{subdir}-{mode_suffix}-access"
                    )

        for fs in finish_args["filesystem"]:
            for resv_dir in [
                ".flatpak-info",
                "app",
                "bin",
                "dev",
                "etc",
                "lib",
                "lib32",
                "lib64",
                "proc",
                "root",
                "run/flatpak",
                "run/host",
                "sbin",
                "usr",
            ]:
                if fs.startswith(f"/{resv_dir}"):
                    self.errors.add(f"finish-args-reserved-{resv_dir}")
                    self.info.add(
                        f"finish-args-reserved-{resv_dir}: finish-args has filesystem access"
                        + f" to {resv_dir} which is reserved internally for Flatpak"
                    )
            if fs.startswith("/home") or fs.startswith("/var/home"):
                self.errors.add("finish-args-absolute-home-path")
                self.info.add(
                    "finish-args-absolute-home-path: finish-args has filesystem access"
                    + " starting with /home or /var/home"
                )
            if re.match(r"^/run/media(?=/\w).+$", fs):
                self.errors.add("finish-args-absolute-run-media-path")
                self.info.add(
                    "finish-args-absolute-home-path: finish-args has filesystem access"
                    + " that is a subdirectory of /run/media"
                )
            if fs.startswith(
                ("xdg-run/dconf", "~/.config/dconf", "home/dconf")
            ) or re.match("^/run/user/.*/dconf", fs):
                self.errors.add("finish-args-direct-dconf-path")
                self.info.add(
                    "finish-args-direct-dconf-path: finish-args"
                    + " has direct access to host dconf path"
                )

        for own_name in finish_args["own-name"]:
            if appid:
                # Values not allowed: appid or appid.*
                # See https://github.com/flathub/flatpak-builder-lint/issues/33
                if own_name == appid or (
                    own_name.startswith(appid) and own_name[len(appid)] == "."
                ):
                    self.errors.add("finish-args-unnecessary-appid-own-name")
            if own_name == "org.freedesktop.*":
                self.errors.add("finish-args-wildcard-freedesktop-own-name")
            if own_name == "org.gnome.*":
                self.errors.add("finish-args-wildcard-gnome-own-name")
            if own_name == "org.kde.*":
                self.errors.add("finish-args-wildcard-kde-own-name")
            if own_name.startswith("org.freedesktop.portal."):
                self.errors.add("finish-args-portal-own-name")
                self.info.add(
                    "finish-args-portal-own-name: finish-args has own-name access"
                    + " to XDG Portal busnames"
                )
            if own_name == "ca.desrt.dconf" or own_name.startswith("ca.desrt.dconf."):
                self.errors.add("finish-args-dconf-own-name")
            if own_name == "org.freedesktop.DBus" or own_name.startswith(
                "org.freedesktop.DBus."
            ):
                self.errors.add("finish-args-freedesktop-dbus-own-name")
                self.info.add(
                    "finish-args-freedesktop-dbus-own-name: finish-args has own-name access to"
                    + " org.freedesktop.DBus or its sub-bus name"
                )
            if own_name == "org.gtk.vfs":
                self.errors.add("finish-args-gvfs-own-name")
            if own_name == "org.freedesktop.Flatpak" or own_name.startswith(
                "org.freedesktop.Flatpak."
            ):
                self.errors.add("finish-args-flatpak-own-name")

        for talk_name in finish_args["talk-name"]:
            if talk_name == "org.freedesktop.*":
                self.errors.add("finish-args-wildcard-freedesktop-talk-name")
            if talk_name == "org.gnome.*":
                self.errors.add("finish-args-wildcard-gnome-talk-name")
            if talk_name == "org.kde.*":
                self.errors.add("finish-args-wildcard-kde-talk-name")
            if talk_name.startswith("org.freedesktop.portal."):
                self.errors.add("finish-args-portal-talk-name")
                self.info.add(
                    "finish-args-portal-talk-name: finish-args has talk-name access"
                    + " to XDG Portal busnames"
                )
            if talk_name == "ca.desrt.dconf" or talk_name.startswith("ca.desrt.dconf."):
                self.errors.add("finish-args-dconf-talk-name")
            if talk_name == "org.freedesktop.DBus" or talk_name.startswith(
                "org.freedesktop.DBus."
            ):
                self.errors.add("finish-args-freedesktop-dbus-talk-name")
                self.info.add(
                    "finish-args-freedesktop-dbus-talk-name: finish-args has talk-name access to"
                    + " org.freedesktop.DBus or its sub-bus name"
                )
            if talk_name == "org.gtk.vfs":
                self.errors.add("finish-args-incorrect-dbus-gvfs")
            if talk_name in ("org.freedesktop.Flatpak", "org.freedesktop.Flatpak.*"):
                self.errors.add("finish-args-flatpak-spawn-access")
                self.info.add(
                    "finish-args-flatpak-spawn-access: finish-args has access"
                    + " to flatpak-spawn"
                )
            if talk_name != "org.freedesktop.Flatpak.*" and talk_name.startswith(
                "org.freedesktop.Flatpak."
            ):
                self.errors.add("finish-args-flatpak-talk-name")

        for sys_own_name in finish_args["system-own-name"]:
            if sys_own_name == "org.freedesktop.*":
                self.errors.add("finish-args-wildcard-freedesktop-system-own-name")
            if sys_own_name == "org.gnome.*":
                self.errors.add("finish-args-wildcard-gnome-system-own-name")
            if sys_own_name == "org.kde.*":
                self.errors.add("finish-args-wildcard-kde-system-own-name")
            if sys_own_name == "org.freedesktop.DBus" or sys_own_name.startswith(
                "org.freedesktop.DBus."
            ):
                self.errors.add("finish-args-freedesktop-dbus-system-own-name")
                self.info.add(
                    "finish-args-freedesktop-dbus-system-own-name: finish-args has system own-name"
                    + " access to org.freedesktop.DBus or its sub-bus name"
                )
            if sys_own_name == "org.freedesktop.Flatpak" or sys_own_name.startswith(
                "org.freedesktop.Flatpak."
            ):
                self.errors.add("finish-args-flatpak-system-own-name")

        for sys_talk_name in finish_args["system-talk-name"]:
            if sys_talk_name == "org.freedesktop.*":
                self.errors.add("finish-args-wildcard-freedesktop-system-talk-name")
            if sys_talk_name == "org.gnome.*":
                self.errors.add("finish-args-wildcard-gnome-system-talk-name")
            if sys_talk_name == "org.kde.*":
                self.errors.add("finish-args-wildcard-kde-system-talk-name")
            if sys_talk_name == "org.freedesktop.DBus" or sys_talk_name.startswith(
                "org.freedesktop.DBus."
            ):
                self.errors.add("finish-args-freedesktop-dbus-system-talk-name")
                self.info.add(
                    "finish-args-freedesktop-dbus-system-talk-name: finish-args has system"
                    + " talk-name access to org.freedesktop.DBus or its sub-bus name"
                )
            if sys_talk_name == "org.freedesktop.Flatpak" or sys_talk_name.startswith(
                "org.freedesktop.Flatpak."
            ):
                self.errors.add("finish-args-flatpak-system-talk-name")

        if (
            "system-bus" in finish_args["socket"]
            or "session-bus" in finish_args["socket"]
        ):
            self.errors.add("finish-args-arbitrary-dbus-access")
            self.info.add(
                "finish-args-arbitrary-dbus-access: finish-args has socket access to"
                + " full system or session bus"
            )

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
                if key == "nodevice":
                    key = "device"
                    value = "!" + value
                if key == "nosocket":
                    key = "socket"
                    value = "!" + value
                if key == "unshare":
                    key = "share"
                    value = "!" + value
                fa[key].add(value)

        self._validate(appid, fa)

    def check_build(self, path: str) -> None:
        metadata = builddir.parse_metadata(path)
        if not metadata:
            return

        if metadata.get("type", False) != "application":
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

    def check_repo(self, path: str) -> None:
        self._populate_ref(path)
        ref = self.repo_primary_ref
        if not ref:
            return
        appid = ref.split("/")[1]

        is_baseapp = appid.endswith(".BaseApp")

        with tempfile.TemporaryDirectory() as tmpdir:
            ostree.extract_subpath(path, ref, "/metadata", tmpdir)
            metadata = builddir.parse_metadata(tmpdir)
            if not metadata:
                return
            permissions = metadata["permissions"]
            if not permissions and not is_baseapp:
                self.errors.add("finish-args-not-defined")
                return
            self._validate(appid, permissions)
