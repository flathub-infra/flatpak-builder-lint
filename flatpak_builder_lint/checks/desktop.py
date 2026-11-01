import errno
import glob
import os
import re
import stat
import subprocess
import tempfile

from gi.repository import GLib

from .. import appstream, builddir, config, ostree
from . import Check

MAX_DESKTOP_FILE_BYTES = 8 * 1024 * 1024


def _open_beneath(root: str, relative: str, *, directory: bool) -> int:
    root_real = os.path.realpath(root)
    resolved = os.path.realpath(os.path.join(root, relative))
    if os.path.commonpath((root_real, resolved)) != root_real:
        raise OSError(errno.EPERM, f"{relative} resolves outside the artifact")

    parts = [] if resolved == root_real else os.path.relpath(resolved, root_real).split(os.sep)
    dir_fd = os.open(root_real, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for index, part in enumerate(parts):
            flags = os.O_RDONLY | os.O_NOFOLLOW
            if index + 1 < len(parts) or directory:
                flags |= os.O_DIRECTORY
            next_fd = os.open(part, flags, dir_fd=dir_fd)
            os.close(dir_fd)
            dir_fd = next_fd
        return dir_fd
    except BaseException:
        os.close(dir_fd)
        raise


def _read_beneath(root: str, relative: str) -> bytes:
    fd = _open_beneath(root, relative, directory=False)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError(errno.EINVAL, f"{relative} is not a regular file")
        chunks = bytearray()
        while len(chunks) <= MAX_DESKTOP_FILE_BYTES:
            chunk = os.read(fd, 65536)
            if not chunk:
                return bytes(chunks)
            chunks += chunk
        raise OSError(errno.EFBIG, f"{relative} is too large")
    finally:
        os.close(fd)


def _list_beneath(root: str, relative: str) -> list[str]:
    fd = _open_beneath(root, relative, directory=True)
    try:
        return os.listdir(fd)
    finally:
        os.close(fd)


class DesktopfileCheck(Check):
    def _read_desktop_file(self, root: str, name: str) -> bytes | None:
        try:
            return _read_beneath(root, f"applications/{name}")
        except OSError as err:
            if err.errno not in (errno.ENOENT, errno.EISDIR, errno.EINVAL):
                self.errors.add("desktop-file-unsafe-path")
                self.info.add(
                    f"desktop-file-unsafe-path: Desktop file: {name}"
                    + " resolves outside the artifact or is not a regular file"
                )
            return None

    def _validate(self, path: str, appid: str) -> None:
        appstream_path = f"{path}/app-info/xmls/{appid}.xml.gz"
        icon_path = f"{path}/icons/hicolor"
        glob_path = f"{icon_path}/*/apps/*"

        if appid.endswith(config.FLATHUB_BASEAPP_IDENTIFIER):
            return

        desktop_files = []
        try:
            desktop_names = _list_beneath(path, "applications")
        except OSError as err:
            desktop_names = []
            if err.errno != errno.ENOENT:
                self.errors.add("desktop-file-unsafe-path")
                self.info.add(
                    "desktop-file-unsafe-path: The applications directory"
                    + " resolves outside the artifact"
                )
        for file in desktop_names:
            if re.match(rf"^{appid}([-.].*)?\.desktop$", file):
                desktop_files.append(file)
        desktop_files.sort()

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
                    + " were found in $FLATPAK_DEST/share/icons/hicolor/$size/apps"
                    + " or $FLATPAK_DEST/share/icons/hicolor/scalable/apps"
                )

            if not len(desktop_files) > 0:
                self.errors.add("desktop-file-not-installed")
                self.info.add(
                    f"desktop-file-not-installed: No desktop file matching {appid}"
                    + " was found in $FLATPAK_DEST/share/applications"
                )

        with tempfile.TemporaryDirectory() as snapshot_dir:
            for file in desktop_files:
                data = self._read_desktop_file(path, file)
                if data is None:
                    continue

                snapshot = os.path.join(snapshot_dir, file)
                with open(snapshot, "wb") as snapshot_file:
                    snapshot_file.write(data)

                env = os.environ.copy()
                env["LANGUAGE"] = "C"
                env["LC_ALL"] = "C"

                cmd = subprocess.run(
                    [
                        "desktop-file-validate",
                        "--no-hints",
                        "--no-warn-deprecated",
                        snapshot,
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                    env=env,
                )
                if cmd.returncode != 0:
                    self.errors.add("desktop-file-failed-validation")
                    self.info.add(
                        f"desktop-file-failed-validation: Desktop file: {os.path.basename(file)}"
                        + " has failed validation. Please see the errors in desktopfile block"
                    )
                    for p in cmd.stdout.decode("utf-8").split(f"{file}:")[1:]:
                        self.desktopfile.add(p.strip())

        primary_data = self._read_desktop_file(path, f"{appid}.desktop")
        if primary_data is None:
            return

        key_file = GLib.KeyFile.new()
        try:
            key_file.load_from_bytes(GLib.Bytes.new(primary_data), GLib.KeyFileFlags.NONE)
        except GLib.Error:
            return

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
        elif len(exect) > 0 and "flatpak run" in exect:
            # desktop files are rewritten only on (re)install, neither
            # exported ref or builddir should have "flatpak run"
            # unless manually added in desktop-file
            # https://github.com/flatpak/flatpak/blob/65bc369a9f7851cc1344d2a767b308050cd66fe3/common/flatpak-transaction.c#L4765
            # flatpak-dir.c: export_desktop_file < rewrite_export_dir
            # < flatpak_rewrite_export_dir < flatpak_dir_deploy
            # < flatpak_dir_deploy_install < flatpak_dir_install
            self.errors.add("desktop-file-exec-has-flatpak-run")
            self.info.add(
                f"desktop-file-exec-has-flatpak-run: Exec key: {exect}" + " uses flatpak run in it"
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
            self.errors.add("desktop-file-low-quality-category")
            self.info.add(
                "desktop-file-low-quality-category: A low quality category was found"
                + f" in the desktop file: {found_cats}"
            )

    def check_build(self, path: str) -> None:
        appid, ref_type = builddir.infer_appid(path), builddir.infer_type(path)
        if not (appid and ref_type) or ref_type == "runtime":
            return

        self._validate(f"{path}/files/share", appid)

    def check_repo(self, path: str) -> None:
        self._populate_refs(path)
        refs = self.repo_primary_refs
        if not refs:
            return
        for ref in refs:
            appid = ref.split("/")[1]

            with tempfile.TemporaryDirectory() as tmpdir:
                for subdir in ("app-info", "applications", "icons"):
                    os.makedirs(os.path.join(tmpdir, subdir), exist_ok=True)
                    ostree.extract_subpath(
                        path, ref, f"files/share/{subdir}", os.path.join(tmpdir, subdir), True
                    )

                self._validate(tmpdir, appid)
