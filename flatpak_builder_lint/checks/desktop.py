import glob
import os
import re
import subprocess
import tempfile

from gi.repository import GLib

from .. import appstream, builddir, config, ostree
from . import Check


def _check_exec(exec_line: str, bin_path: str) -> tuple[bool, str | None]:
    ret = (False, None)

    try:
        _, argv = GLib.shell_parse_argv(exec_line)  # type: ignore[misc]
    except GLib.Error:
        return ret

    if not argv:
        return ret

    skip_prgs = ("env", "export", "bash", "sh", "flatpak")
    skip_unlikely = (
        "%f",
        "%F",
        "%u",
        "%U",
        "%d",
        "%D",
        "%n",
        "%N",
        "%i",
        "%c",
        "%k",
        "%v",
        "%m",
        "@@",
        "--",
        "-",
    )

    args: list[str] = [
        arg
        for arg in argv
        if not (arg.endswith(skip_prgs) or arg.startswith(skip_unlikely)) and "=" not in arg
    ]
    if not args:
        return ret

    executable = args[0]
    exect_path = os.path.join(bin_path, os.path.basename(executable))
    # The linter runs outside of Flatpak's context. So we can't use
    # things like GLib.find_program_in_path() which would try to find
    # the program in the parent PATH. Additionally symlinks might
    # also be broken since we are extracting only bin directory and they
    # may point to the path inside the sandbox anyways. We don't want
    # to extract everything from the repo to avoid running out of space
    if os.path.lexists(exect_path):
        return (True, executable)
    return (False, executable)


class DesktopfileCheck(Check):
    def _validate(self, path: str, appid: str) -> None:
        bin_path = f"{path}/bin"
        appstream_path = f"{path}/share/app-info/xmls/{appid}.xml.gz"
        desktopfiles_path = f"{path}/share/applications"
        icon_path = f"{path}/share/icons/hicolor"
        glob_path = f"{icon_path}/*/apps/*"

        if appid.endswith(config.FLATHUB_BASEAPP_IDENTIFIER):
            return

        desktop_files = []
        if os.path.exists(desktopfiles_path):
            desktop_files = [
                file
                for file in os.listdir(desktopfiles_path)
                if os.path.isfile(f"{desktopfiles_path}/{file}")
                and re.match(rf"^{appid}([-.].*)?\.desktop$", file)
            ]

        icon_list = []
        icon_files_list = []
        if os.path.exists(icon_path):
            icon_list = [
                file
                for file in glob.glob(glob_path)
                if re.match(rf"^{appid}([-.].*)?$", os.path.basename(file)) and os.path.isfile(file)
            ]
            icon_files_list = [os.path.basename(i) for i in icon_list]

        if not os.path.exists(appstream_path):
            return

        if len(appstream.components(appstream_path)) != 1:
            return

        aps_ctype = appstream.component_type(appstream_path)

        if aps_ctype not in config.FLATHUB_APPSTREAM_TYPES_APPS:
            return

        is_console = aps_ctype == config.FLATHUB_APPSTREAM_TYPES_CONSOLE

        if not is_console:
            if not len(icon_list) > 0:
                self.errors.add("no-exportable-icon-installed")
                self.info.add(
                    f"no-exportable-icon-installed: No PNG or SVG icons named by {appid}"
                    + " were found in /app/share/icons/hicolor/$size/apps"
                    + " or /app/share/icons/hicolor/scalable/apps"
                )

            if not len(desktop_files) > 0:
                self.errors.add("desktop-file-not-installed")
                self.info.add(
                    f"desktop-file-not-installed: No desktop file matching {appid}"
                    + " was found in /app/share/applications"
                )

        for file in desktop_files:
            if os.path.exists(f"{desktopfiles_path}/{file}"):
                cmd = subprocess.run(
                    [
                        "desktop-file-validate",
                        "--no-hints",
                        "--no-warn-deprecated",
                        f"{desktopfiles_path}/{file}",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                if cmd.returncode != 0:
                    self.errors.add("desktop-file-failed-validation")
                    self.info.add(
                        f"desktop-file-failed-validation: Desktop file: {file}"
                        + " has failed validation. Please see the errors in desktopfile block"
                    )
                    for p in cmd.stdout.decode("utf-8").split(f"{file}:")[1:]:
                        self.desktopfile.add(p.strip())

        if os.path.exists(f"{desktopfiles_path}/{appid}.desktop"):
            key_file = GLib.KeyFile.new()
            key_file.load_from_file(f"{desktopfiles_path}/{appid}.desktop", GLib.KeyFileFlags.NONE)

            if key_file.get_start_group() != "Desktop Entry":
                raise GLib.Error("Unknown start group in desktop file.")

            try:
                icon = key_file.get_string("Desktop Entry", "Icon")
            except GLib.Error:
                icon = None

            if icon is None:
                if not is_console:
                    self.errors.add("desktop-file-icon-key-absent")
            else:
                if not len(icon) > 0:
                    self.errors.add("desktop-file-icon-key-empty")
                if len(icon) > 0:
                    if not re.match(rf"^{appid}([-.].*)?$", f"{icon}"):
                        self.errors.add("desktop-file-icon-key-wrong-value")
                        self.info.add(
                            "desktop-file-icon-key-wrong-value: Icon key in desktop file has"
                            + f" wrong value: {icon}"
                        )
                    if icon_files_list:
                        found_icons = set(icon_files_list)
                        if not any(
                            k in icon_files_list
                            for k in (
                                icon,
                                icon + ".png",
                                icon + ".svg",
                                icon + ".svgz",
                            )
                        ):
                            self.errors.add("desktop-file-icon-not-installed")
                            self.info.add(
                                "desktop-file-icon-not-installed: An icon named by value of"
                                + f" icon key in desktop file: {icon} was not found."
                                + f" Found icons: {found_icons}"
                            )

            try:
                exect = key_file.get_string("Desktop Entry", "Exec")
            except GLib.Error:
                exect = None

            if exect is None:
                # https://gitlab.freedesktop.org/xdg/desktop-file-utils/-/issues/6
                self.errors.add("desktop-file-exec-key-absent")
            elif len(exect) > 0:
                if "flatpak run" in exect:
                    # desktop files are rewritten only on (re)install, neither
                    # exported ref or builddir should have "flatpak run"
                    # unless manually added in desktop-file
                    # https://github.com/flatpak/flatpak/blob/65bc369a9f7851cc1344d2a767b308050cd66fe3/common/flatpak-transaction.c#L4765
                    # flatpak-dir.c: export_desktop_file < rewrite_export_dir
                    # < flatpak_rewrite_export_dir < flatpak_dir_deploy
                    # < flatpak_dir_deploy_install < flatpak_dir_install
                    self.errors.add("desktop-file-exec-has-flatpak-run")
                    self.info.add(
                        f"desktop-file-exec-has-flatpak-run: Exec key: {exect}"
                        + " uses flatpak run in it"
                    )
                exec_check_ret, calc_exect = _check_exec(exect, bin_path)
                if not exec_check_ret:
                    self.errors.add("desktop-file-exec-not-found-in-bindir")
                    self.info.add(
                        f"desktop-file-exec-not-found-in-bindir: The binary '{calc_exect}'"
                        + " calculated from the 'Exec' key was not found in bin directory"
                    )

            try:
                hidden = key_file.get_boolean("Desktop Entry", "Hidden")
            except GLib.Error:
                hidden = None

            if hidden is True:
                self.errors.add("desktop-file-is-hidden")
                self.info.add(
                    "desktop-file-is-hidden: Desktop file has the Hidden key set to true."
                    + " Console applications should use NoDisplay=true to hide desktop files"
                )

            try:
                nodisplay = key_file.get_boolean("Desktop Entry", "NoDisplay")
            except GLib.Error:
                nodisplay = None

            if nodisplay is True and not is_console:
                self.errors.add("desktop-file-is-nodisplay")
                self.info.add(
                    "desktop-file-is-nodisplay: Desktop file has the NoDisplay key set to true"
                )

            # check only when console application does not hide
            # the desktop file. desktop-file-validate fails on empty
            # value of terminal key
            if is_console and nodisplay in (
                False,
                None,
            ):
                try:
                    terminal = key_file.get_boolean("Desktop Entry", "Terminal")
                except GLib.Error:
                    terminal = None

                if terminal in (False, None):
                    self.errors.add("desktop-file-terminal-key-not-true")
                    self.info.add(
                        "desktop-file-terminal-key-not-true: Desktop file for console application"
                        + " is set to display but does not have Terminal=true"
                    )
            try:
                cats = set(key_file.get_string_list("Desktop Entry", "Categories"))
            except GLib.Error:
                cats = None

            # https://github.com/ximion/appstream/blob/a98d98ec1b75d7e9402d8d103802992415075d2f/src/as-utils.c#L1337-L1364
            # appstreamcli filters these out during compose, "GUI"
            # is caught by desktop-file-validate
            block = {
                "GTK",
                "Qt",
                "KDE",
                "GNOME",
                "Motif",
                "Java",
                "Application",
                "XFCE",
                "DDE",
            }
            if cats is not None and len(cats) > 0 and cats.issubset(block):
                found_cats = cats.intersection(block)
                self.warnings.add("desktop-file-low-quality-category")
                self.info.add(
                    "desktop-file-low-quality-category: A low quality category was found"
                    + f" in the desktop file: {found_cats}"
                )

    def check_build(self, path: str) -> None:
        appid, ref_type = builddir.infer_appid(path), builddir.infer_type(path)
        if not (appid and ref_type) or ref_type == "runtime":
            return

        self._validate(f"{path}/files", appid)

    def check_repo(self, path: str) -> None:
        self._populate_refs(path)
        refs = self.repo_primary_refs
        if not refs:
            return
        for ref in refs:
            appid = ref.split("/")[1]

            with tempfile.TemporaryDirectory() as tmpdir:
                for subdir in ("app-info", "applications", "icons"):
                    dest = os.path.join(tmpdir, os.path.join("share", subdir))
                    os.makedirs(dest, exist_ok=True)
                    ostree.extract_subpath(path, ref, f"files/share/{subdir}", dest, True)

                os.makedirs(dest := os.path.join(tmpdir, "bin"), exist_ok=True)
                ostree.extract_subpath(path, ref, "files/bin", dest, True)

                self._validate(tmpdir, appid)
