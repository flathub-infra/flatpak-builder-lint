import re
import tempfile
from collections import defaultdict
from collections.abc import Mapping
from typing import Any

import gi

from .. import builddir, config, ostree
from . import Check

gi.require_version("AppStream", "1.0")
from gi.repository import AppStream  # noqa: E402


def _fs_value_matches_prefix(input_path: str, prefix: str, subdirs: bool = True) -> bool:
    if subdirs:
        pattern = rf"^{re.escape(prefix)}(?:/.*)?(?::(create|rw|ro))?$"
    else:
        pattern = rf"^{re.escape(prefix)}/?(?::(create|rw|ro))?$"

    return re.match(pattern, input_path) is not None


class FinishArgsCheck(Check):
    def _validate(self, appid: str | None, finish_args: dict[str, set[str]]) -> None:
        init_ver = finish_args.get("required-flatpak")
        flatpak_version = None
        if isinstance(init_ver, (set | list)):
            flatpak_version = next(iter(init_ver))
        if isinstance(init_ver, str):
            flatpak_version = init_ver.split(";", 1)[0]

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

        if "gpg-agent" in finish_args["socket"]:
            self.errors.add("finish-args-has-socket-gpg-agent")

        if "ssh-auth" in finish_args["socket"]:
            self.errors.add("finish-args-has-socket-ssh-auth")

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
            if dev in ("input", "usb"):
                if "required-flatpak" not in finish_args:
                    self.errors.add("finish-args-no-required-flatpak")
                    self.info.add(
                        "finish-args-no-required-flatpak: finish-args has 'input' or 'usb'"
                        + " device but no minimum Flatpak version. Use 'all' for backwards"
                        + " compat or specify '--require-version='"
                    )
                if flatpak_version is not None and not AppStream.vercmp_test_match(
                    flatpak_version,
                    AppStream.RelationCompare.GE,
                    "1.16.0",
                    AppStream.VercmpFlags.NONE,
                ):
                    self.errors.add("finish-args-insufficient-required-flatpak")
                    self.info.add(
                        "finish-args-insufficient-required-flatpak: finish-args has"
                        + " 'input' or 'usb' device but 'require-version' is not >=1.16.0"
                    )
                if dev == "input":
                    self.errors.add("finish-args-has-dev-input")
                    self.info.add(
                        "finish-args-has-dev-input: This permissions is not backwards"
                        + " compatible with a supported Flatpak release 1.14.x and"
                        + " requires an exception"
                    )
                if dev == "usb":
                    self.errors.add("finish-args-has-dev-usb")
                    self.info.add(
                        "finish-args-has-dev-input: This permissions is not backwards"
                        + " compatible with a supported Flatpak release 1.14.x and"
                        + " requires an exception"
                    )

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
            for resv_dir in (
                "/.flatpak-info",
                "/app",
                "/bin",
                "/dev",
                "/etc",
                "/lib",
                "/lib32",
                "/lib64",
                "/proc",
                "/root",
                "/run/flatpak",
                "/run/host",
                "/sbin",
                "/usr",
            ):
                if _fs_value_matches_prefix(fs, resv_dir):
                    self.errors.add(f"finish-args-reserved-{resv_dir.lstrip('/')}")
                    self.info.add(
                        f"finish-args-reserved-{resv_dir.lstrip('/')}: finish-args has filesystem"
                        + f" access to {resv_dir} which is reserved internally for Flatpak"
                    )

            if re.fullmatch(r"^(home|host|host-root|~/?)(:rw|:create|:ro)?$", fs):
                if fs.startswith("host-root"):
                    path = "host-root"
                elif fs.startswith("host"):
                    path = "host"
                else:
                    path = "home"

                if fs.endswith(":ro"):
                    self.errors.add(f"finish-args-{path}-ro-filesystem-access")
                else:
                    self.errors.add(f"finish-args-{path}-filesystem-access")

            if any(
                _fs_value_matches_prefix(fs, prefix, False)
                for prefix in (
                    "~/.config",
                    "home/.config",
                )
            ):
                self.errors.add("finish-args-full-home-config-access")

            if any(
                _fs_value_matches_prefix(fs, prefix, False)
                for prefix in (
                    "~/.cache",
                    "home/.cache",
                )
            ):
                self.errors.add("finish-args-full-home-cache-access")

            if any(
                _fs_value_matches_prefix(fs, prefix, False)
                for prefix in (
                    "~/.local",
                    "home/.local",
                )
            ):
                self.errors.add("finish-args-full-home-local-access")

            if any(
                _fs_value_matches_prefix(fs, prefix, False)
                for prefix in (
                    "~/.local/share",
                    "home/.local/share",
                )
            ):
                self.errors.add("finish-args-full-home-local-share-access")

            if any(
                _fs_value_matches_prefix(fs, prefix, False)
                for prefix in (
                    "~/.config/autostart",
                    "home/.config/autostart",
                )
            ):
                self.errors.add("finish-args-autostart-filesystem-access")

            if any(
                _fs_value_matches_prefix(fs, prefix)
                for prefix in (
                    "~/.config/systemd",
                    "home/.config/systemd",
                )
            ):
                self.errors.add("finish-args-systemd-filesystem-access")

            if any(
                _fs_value_matches_prefix(fs, prefix, False)
                for prefix in (
                    "~/.local/share/applications",
                    "home/.local/share/applications",
                )
            ):
                self.errors.add("finish-args-desktopfile-filesystem-access")

            if any(
                _fs_value_matches_prefix(fs, prefix)
                for prefix in (
                    "~/.ssh",
                    "home/.ssh",
                )
            ):
                self.errors.add("finish-args-ssh-filesystem-access")

            if any(
                _fs_value_matches_prefix(fs, prefix)
                for prefix in (
                    "~/.gnupg",
                    "home/.gnupg",
                )
            ):
                self.errors.add("finish-args-gnupg-filesystem-access")

            if any(
                _fs_value_matches_prefix(fs, prefix)
                for prefix in (
                    "/home",
                    "/var/home",
                )
            ):
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

            if any(
                _fs_value_matches_prefix(fs, prefix)
                for prefix in (
                    "xdg-run/dconf",
                    "~/.config/dconf",
                    "home/.config/dconf",
                )
            ) or re.match("^/run/user/.*/dconf", fs):
                self.errors.add("finish-args-direct-dconf-path")
                self.info.add(
                    "finish-args-direct-dconf-path: finish-args"
                    + " has direct access to host dconf path"
                )

            if any(
                _fs_value_matches_prefix(fs, prefix)
                for prefix in (
                    "~/.var/app",
                    "home/.var/app",
                )
            ):
                self.errors.add("finish-args-flatpak-appdata-folder-access")

            if any(
                _fs_value_matches_prefix(fs, prefix)
                for prefix in (
                    "~/.icons",
                    "home/.icons",
                )
            ):
                self.errors.add("finish-args-legacy-icon-folder-permission")

            if any(
                _fs_value_matches_prefix(fs, prefix)
                for prefix in (
                    "~/.fonts",
                    "home/.fonts",
                )
            ):
                self.errors.add("finish-args-legacy-font-folder-permission")

            if any(
                _fs_value_matches_prefix(fs, prefix)
                for prefix in (
                    "~/.themes",
                    "home/.themes",
                )
            ):
                self.errors.add("finish-args-incorrect-theme-folder-permission")

            if _fs_value_matches_prefix(fs, "/var/lib/flatpak"):
                self.errors.add("finish-args-flatpak-system-folder-access")

            if any(
                _fs_value_matches_prefix(fs, prefix)
                for prefix in (
                    "~/.local/share/flatpak",
                    "home/.local/share/flatpak",
                )
            ):
                self.errors.add("finish-args-flatpak-user-folder-access")

            if _fs_value_matches_prefix(fs, "/tmp"):  # noqa: S108
                self.errors.add("finish-args-host-tmp-access")

            if (
                fs.startswith("/var")
                and not fs.startswith(
                    (
                        "/var/cache",
                        "/var/config",
                        "/var/data",
                        "/var/tmp",  # noqa: S108
                        "/var/lib/flatpak",
                        "/var/home",
                    )
                )
                and _fs_value_matches_prefix(fs, "/var")
            ):
                self.errors.add("finish-args-host-var-access")

        for own_name in finish_args["own-name"]:
            if appid:
                if own_name == appid or (
                    own_name.startswith(appid) and own_name[len(appid)] == "."
                ):
                    continue
                if own_name.startswith("org.mpris.MediaPlayer2."):
                    continue

            if own_name.endswith(".*"):
                own_name_prefix, own_name_name = "wildcard", own_name[:-2]
                own_name_err_string = (
                    f"finish-args-own-name-"
                    f"{own_name_prefix + '-' if own_name_prefix else ''}"
                    f"{own_name_name}"
                )
                self.errors.add(own_name_err_string)
            else:
                own_name_err_string = f"finish-args-own-name-{own_name}"
                self.errors.add(own_name_err_string)

        if finish_args.get("none-name"):
            self.errors.add("finish-args-uses-no-talk-name")

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
            if talk_name.startswith("org.freedesktop.impl.portal."):
                cpt = talk_name.split(".")[-1].lower()
                self.errors.add(f"finish-args-portal-impl-{cpt}-talk-name")
            if talk_name == "org.freedesktop.systemd1" or talk_name.startswith(
                "org.freedesktop.systemd1."
            ):
                self.errors.add("finish-args-systemd1-talk-name")
            if talk_name == "org.freedesktop.login1" or talk_name.startswith(
                "org.freedesktop.login1."
            ):
                self.errors.add("finish-args-login1-talk-name")
            if talk_name == "org.kde.KWin" or talk_name.startswith("org.kde.KWin."):
                self.errors.add("finish-args-kwin-talk-name")
            if talk_name == "org.kde.plasmashell" or talk_name.startswith("org.kde.plasmashell."):
                self.errors.add("finish-args-plasmashell-talk-name")

        for sys_own_name in finish_args["system-own-name"]:
            sys_own_name_prefix: str | None
            if sys_own_name.endswith(".*"):
                sys_own_name_prefix, sys_own_name_name = "wildcard", sys_own_name[:-2]
            else:
                sys_own_name_prefix, sys_own_name_name = None, sys_own_name

            sys_own_name_err_string = (
                f"finish-args-system-own-name-"
                f"{sys_own_name_prefix + '-' if sys_own_name_prefix else ''}{sys_own_name_name}"
            )
            self.errors.add(sys_own_name_err_string)

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
            if sys_talk_name.startswith("org.freedesktop.impl.portal."):
                cpt = sys_talk_name.split(".")[-1].lower()
                self.errors.add(f"finish-args-portal-impl-{cpt}-system-talk-name")
            if sys_talk_name == "org.freedesktop.systemd1" or sys_talk_name.startswith(
                "org.freedesktop.systemd1."
            ):
                self.errors.add("finish-args-systemd1-system-talk-name")
            if sys_talk_name == "org.freedesktop.login1" or sys_talk_name.startswith(
                "org.freedesktop.login1."
            ):
                self.errors.add("finish-args-login1-system-talk-name")
            if sys_talk_name == "org.kde.KWin" or sys_talk_name.startswith("org.kde.KWin."):
                self.errors.add("finish-args-kwin-system-talk-name")
            if sys_talk_name == "org.kde.plasmashell" or sys_talk_name.startswith(
                "org.kde.plasmashell."
            ):
                self.errors.add("finish-args-plasmashell-system-talk-name")

        if "system-bus" in finish_args["socket"] or "session-bus" in finish_args["socket"]:
            self.errors.add("finish-args-arbitrary-dbus-access")
            self.info.add(
                "finish-args-arbitrary-dbus-access: finish-args has socket access to"
                + " full system or session bus"
            )

    def check_manifest(self, manifest: Mapping[str, Any]) -> None:
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
                if key == "require-version":
                    key = "required-flatpak"
                if key == "nodevice":
                    key = "device"
                    value = "!" + value
                if key == "nosocket":
                    key = "socket"
                    value = "!" + value
                if key == "unshare":
                    key = "share"
                    value = "!" + value
                if key in ("no-talk-name", "system-no-talk-name"):
                    key = "none-name"
                if key == "socket-if":
                    key = "socket"
                    value = f"if:{value}"
                if key == "device-if":
                    key = "device"
                    value = f"if:{value}"
                fa[key].add(value)

        self._validate(appid, fa)

    def check_build(self, path: str) -> None:
        appid, ref_type = builddir.infer_appid(path), builddir.infer_type(path)
        if not (appid and ref_type) or ref_type == "runtime":
            return

        metadata = builddir.parse_metadata(path)
        if not metadata:
            return

        raw_perms = metadata.get("permissions")
        permissions: dict[str, set[str]] = raw_perms if isinstance(raw_perms, dict) else {}

        if not permissions and not appid.endswith(config.FLATHUB_BASEAPP_IDENTIFIER):
            self.errors.add("finish-args-not-defined")
            return

        self._validate(appid, permissions)

    def check_repo(self, path: str) -> None:
        self._populate_refs(path)
        refs = self.repo_primary_refs
        if not refs:
            return
        for ref in refs:
            appid = ref.split("/")[1]

            with tempfile.TemporaryDirectory() as tmpdir:
                ostree.extract_subpath(path, ref, "/metadata", tmpdir)
                metadata = builddir.parse_metadata(tmpdir)
                if not metadata:
                    return
                raw_perms = metadata.get("permissions")
                permissions: dict[str, set[str]] = raw_perms if isinstance(raw_perms, dict) else {}
                if not (permissions or appid.endswith(config.FLATHUB_BASEAPP_IDENTIFIER)):
                    self.errors.add("finish-args-not-defined")
                    return
                self._validate(appid, permissions)
