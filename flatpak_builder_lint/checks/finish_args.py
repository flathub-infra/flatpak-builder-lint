import re
import tempfile
from collections import defaultdict

from .. import builddir, config, ostree
from . import Check


class FinishArgsCheck(Check):
    def _validate(self, appid: str | None, finish_args: dict[str, set[str]]) -> None:
        if "x11" in finish_args["socket"] and "fallback-x11" in finish_args["socket"]:
            self.errors.add("finish-args-contains-both-x11-and-fallback")

        if "x11" in finish_args["socket"] and "wayland" in finish_args["socket"]:
            self.errors.add("finish-args-contains-both-x11-and-wayland")

        if (
            "x11" in finish_args["socket"] or "fallback-x11" in finish_args["socket"]
        ) and "ipc" not in finish_args["share"]:
            self.errors.add("finish-args-x11-without-ipc")

        if "fallback-x11" in finish_args["socket"] and "wayland" not in finish_args["socket"]:
            self.errors.add("finish-args-fallback-x11-without-wayland")
            self.info.add(
                "finish-args-fallback-x11-without-wayland: finish-args has fallback-x11"
                + " but no wayland socket"
            )

        if "wayland" in finish_args["socket"] and (
            "x11" not in finish_args["socket"] and "fallback-x11" not in finish_args["socket"]
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
                    mode_src = next(i for i in modes if fs.endswith(i))
                    mode_suffix = mode_src.split(":", 1)[1]

                if re.match(regexp_arbitrary, fs):
                    self.errors.add(f"finish-args-arbitrary-{xdg_dir}-{mode_suffix}-access")
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
            if fs.startswith(("/home", "/var/home")):
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
            if fs.startswith(("xdg-run/dconf", "~/.config/dconf", "home/dconf")) or re.match(
                "^/run/user/.*/dconf", fs
            ):
                self.errors.add("finish-args-direct-dconf-path")
                self.info.add(
                    "finish-args-direct-dconf-path: finish-args"
                    + " has direct access to host dconf path"
                )

            if fs.startswith(("~/.var/app", "home/.var/app")):
                self.errors.add("finish-args-flatpak-appdata-folder-access")

            if fs.startswith("/var/lib/flatpak"):
                self.errors.add("finish-args-flatpak-system-folder-access")

            if fs.startswith(("~/.local/share/flatpak", "home/.local/share/flatpak")):
                self.errors.add("finish-args-flatpak-user-folder-access")

            if fs.startswith("/tmp"):  # noqa: S108
                self.errors.add("finish-args-host-tmp-access")

            if fs.startswith("/var") and not fs.startswith(
                ("/var/cache", "/var/config", "/var/data", "/var/tmp", "/var/lib/flatpak")  # noqa: S108
            ):
                self.errors.add("finish-args-host-var-access")

        for own_name in finish_args["own-name"]:
            # Values not allowed: appid or appid.*
            # See https://github.com/flathub/flatpak-builder-lint/issues/33
            if appid and (
                own_name == appid or (own_name.startswith(appid) and own_name[len(appid)] == ".")
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
            if own_name == "org.freedesktop.DBus" or own_name.startswith("org.freedesktop.DBus."):
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
            if appid and own_name == f"org.mpris.MediaPlayer2.{appid}":
                self.errors.add("finish-args-mpris-flatpak-id-own-name")

        for talk_name in finish_args["talk-name"]:
            # Values not allowed: appid or appid.*
            # An own-name implies talk-name
            # See https://docs.flatpak.org/en/latest/flatpak-command-reference.html
            # session bus policy
            # > The application can own the bus name or names (as well as all the above)
            # https://github.com/flatpak/flatpak/pull/5582#discussion_r1384797147
            if appid and (
                talk_name == appid or (talk_name.startswith(appid) and talk_name[len(appid)] == ".")
            ):
                self.errors.add("finish-args-unnecessary-appid-talk-name")
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
            if talk_name == "org.freedesktop.DBus" or talk_name.startswith("org.freedesktop.DBus."):
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
                    "finish-args-flatpak-spawn-access: finish-args has access" + " to flatpak-spawn"
                )
            if talk_name != "org.freedesktop.Flatpak.*" and talk_name.startswith(
                "org.freedesktop.Flatpak."
            ):
                self.errors.add("finish-args-flatpak-talk-name")

            if talk_name == "org.freedesktop.Secrets":
                self.errors.add("finish-args-incorrect-secret-service-talk-name")
                self.info.add(
                    "finish-args-incorrect-secret-service-talk-name: The name is in lower case"
                    + " org.freedesktop.secrets"
                )
            if appid and talk_name == f"org.mpris.MediaPlayer2.{appid}":
                self.errors.add("finish-args-mpris-flatpak-id-talk-name")

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
            if appid and sys_own_name == f"org.mpris.MediaPlayer2.{appid}":
                self.errors.add("finish-args-mpris-flatpak-id-system-own-name")

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
            if appid and sys_talk_name == f"org.mpris.MediaPlayer2.{appid}":
                self.errors.add("finish-args-mpris-flatpak-id-system-talk-name")

        if "system-bus" in finish_args["socket"] or "session-bus" in finish_args["socket"]:
            self.errors.add("finish-args-arbitrary-dbus-access")
            self.info.add(
                "finish-args-arbitrary-dbus-access: finish-args has socket access to"
                + " full system or session bus"
            )

    def check_manifest(self, manifest: dict) -> None:
        appid = manifest.get("id")

        is_baseapp = bool(
            isinstance(appid, str) and appid.endswith(config.FLATHUB_BASEAPP_IDENTIFIER)
        )

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
        appid, ref_type = builddir.infer_appid(path), builddir.infer_type(path)
        if not (appid and ref_type) or ref_type == "runtime":
            return

        metadata = builddir.parse_metadata(path)
        if not metadata:
            return

        permissions = metadata.get("permissions", {})
        if not permissions and not appid.endswith(config.FLATHUB_BASEAPP_IDENTIFIER):
            self.errors.add("finish-args-not-defined")
            return

        self._validate(appid, permissions)

    def check_repo(self, path: str) -> None:
        self._populate_ref(path)
        ref = self.repo_primary_ref
        if not ref:
            return
        appid = ref.split("/")[1]

        with tempfile.TemporaryDirectory() as tmpdir:
            ostree.extract_subpath(path, ref, "/metadata", tmpdir)
            metadata = builddir.parse_metadata(tmpdir)
            if not metadata:
                return
            permissions = metadata.get("permissions", {})
            if not (permissions or appid.endswith(config.FLATHUB_BASEAPP_IDENTIFIER)):
                self.errors.add("finish-args-not-defined")
                return
            self._validate(appid, permissions)
