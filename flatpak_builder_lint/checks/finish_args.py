import re
import tempfile
from collections import defaultdict
from typing import Optional, Set

from .. import builddir, ostree
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

        if "wayland" in finish_args["socket"] and (
            "x11" not in finish_args["socket"]
            and "fallback-x11" not in finish_args["socket"]
        ):
            self.errors.add("finish-args-only-wayland")

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

        for xdg_dir in ["xdg-data", "xdg-config", "xdg-cache"]:
            regexp_arbitrary = f"^{xdg_dir}(:(create|rw|ro)?)?$"
            regexp_unnecessary = f"^{xdg_dir}(\\/.*)?(:(create|rw|ro)?)?$"
            for fs in finish_args["filesystem"]:
                # This is inherited by apps from the KDE runtime
                if fs == "xdg-config/kdeglobals:ro":
                    continue

                if re.match(regexp_arbitrary, fs):
                    self.errors.add(f"finish-args-arbitrary-{xdg_dir}-access")
                elif re.match(regexp_unnecessary, fs):
                    self.errors.add(f"finish-args-unnecessary-{xdg_dir}-access")

        for fs in finish_args["filesystem"]:
            for resv_dir in [
                ".flatpak-info",
                "app",
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
            if fs.startswith("/home") or fs.startswith("/var/home"):
                self.errors.add("finish-args-absolute-home-path")
            if re.match(r"^/run/media(?=/\w).+$", fs):
                self.errors.add("finish-args-absolute-run-media-path")
            if fs.startswith("host") and fs.endswith(":create"):
                self.errors.add("finish-args-redundant-host-create")
            if fs.startswith("home") and fs.endswith(":create") and "/" not in fs:
                self.errors.add("finish-args-redundant-home-create")
            if any(
                [
                    i in finish_args["filesystem"]
                    for i in (
                        "host",
                        "host:rw",
                        "host-etc",
                        "host-etc:rw",
                        "host-os",
                        "host-os:rw",
                    )
                ]
            ):
                # :create might be needed for some apps, for example
                # ~/Mail:create. They will go through exceptions
                if fs.startswith(("home", "~")) and not fs.endswith(":ro"):
                    self.errors.add("finish-args-redundant-home-and-host")
            if any(
                [
                    i in finish_args["filesystem"]
                    for i in (
                        "host:ro" "host-etc:ro",
                        "host-os:ro",
                    )
                ]
            ):
                if fs.startswith(("home", "~")) and fs.endswith(":ro"):
                    self.errors.add("finish-args-redundant-home-and-host")
            if any(
                [
                    i in finish_args["filesystem"]
                    for i in (
                        "home",
                        "home:rw",
                    )
                ]
            ):
                # :create might be needed for some apps, for example
                # ~/Mail:create. They will go through exceptions
                if fs.startswith("~") and not fs.endswith(":ro"):
                    self.errors.add("finish-args-redundant-home-path")
            if "home:ro" in finish_args["filesystem"]:
                if fs.startswith("~") and fs.endswith(":ro"):
                    self.errors.add("finish-args-redundant-home-path")

        pairs = (
            ("host", "home"),
            ("host", "home:rw"),
            ("host:rw", "home"),
            ("host:rw", "home:rw"),
            ("host:ro", "home:ro"),
            ("host-etc", "home"),
            ("host-etc:rw", "home:rw"),
            ("host-etc", "home:rw"),
            ("host-etc:rw", "home"),
            ("host-etc:ro", "home:ro"),
            ("host-os", "home"),
            ("host-os", "home:rw"),
            ("host-os:rw", "home"),
            ("host-os:rw", "home:rw"),
            ("host-os:ro", "home:ro"),
            # writeable host implies writeable home
            # :ro is meaningless with home in that case
            # as host rw takes precedence
            ("host", "home:ro"),
            ("host:rw", "home:ro"),
            ("host-etc", "home:ro"),
            ("host-etc:rw", "home:ro"),
            ("host-os", "home:ro"),
            ("host-os:rw", "home:ro"),
        )
        if any(all(k in finish_args["filesystem"] for k in p) for p in pairs):
            self.errors.add("finish-args-redundant-home-and-host")

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

        for talk_name in finish_args["talk-name"]:
            if talk_name == "org.freedesktop.*":
                self.errors.add("finish-args-wildcard-freedesktop-talk-name")
            if talk_name == "org.gnome.*":
                self.errors.add("finish-args-wildcard-gnome-talk-name")
            if talk_name == "org.kde.*":
                self.errors.add("finish-args-wildcard-kde-talk-name")
            if talk_name.startswith("org.freedesktop.portal."):
                self.errors.add("finish-args-portal-talk-name")

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
            if "shm" not in finish_args["device"]:
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
            ret = ostree.extract_subpath(path, ref, "/metadata", tmpdir)
            if ret["returncode"] != 0:
                raise RuntimeError("Failed to extract ostree repo")

            metadata = builddir.parse_metadata(tmpdir)
            if not metadata:
                return

            permissions = metadata["permissions"]
            if not permissions and not is_baseapp:
                self.errors.add("finish-args-not-defined")
                return

            self._validate(appid, permissions)
