import os
import subprocess
import tempfile
from typing import Optional, Set

from .. import appstream, builddir, ostree
from . import Check


class DesktopfileCheck(Check):
    def _load(self, path: str, appid: str) -> Optional[dict]:
        appstream_path = f"{path}/files/share/app-info/xmls/{appid}.xml.gz"
        desktop_path = f"{path}/files/share/applications/{appid}.desktop"

        if appid.endswith(".BaseApp"):
            return None

        if not os.path.exists(appstream_path):
            self.errors.add("appstream-missing-appinfo-file")
            return None

        if len(appstream.components(appstream_path)) != 1:
            self.errors.add("appstream-multiple-components")
            return None

        if appstream.component_type(appstream_path) not in (
            "desktop",
            "desktop-application",
        ):
            return None

        if not os.path.exists(desktop_path):
            self.errors.add("desktop-file-not-installed")

        if os.path.exists(desktop_path):
            cmd = subprocess.run(
                [
                    "desktop-file-validate",
                    "--no-hints",
                    "--no-warn-deprecated",
                    desktop_path,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            if cmd.returncode != 0:
                self.errors.add("desktop-file-failed-validation")
                for p in cmd.stdout.decode("utf-8").split(f"{desktop_path}:")[1:]:
                    self.desktopfile.add(p.strip())
            data: dict[str, dict[str, int | str]] = {}
            with open(desktop_path, "r", encoding="utf-8") as file:
                for line in file:
                    line = line.strip()
                    if line.startswith("#") or line == "" or line == "\n":
                        continue
                    if line.startswith("[") and line.endswith("]"):
                        group = line[1:-1]
                        data[group] = {}
                    if "=" in line:
                        key = line.split("=", 1)[0]
                        value = line.split("=", 1)[1]
                        data[group][key] = value
                return data
        return None

    def _validate(self, path: str, appid: str) -> None:
        d = self._load(path, appid)
        if d is not None:
            try:
                icon = d["Desktop Entry"]["Icon"]
                if not len(icon) > 0:
                    self.errors.add("desktop-file-icon-key-empty")
                if len(icon) > 0 and icon != appid:
                    self.errors.add("desktop-file-icon-key-wrong-value")
            except KeyError:
                self.errors.add("desktop-file-icon-key-absent")
                pass

            try:
                exect = d["Desktop Entry"]["Exec"]
                # https://github.com/flatpak/flatpak/commit/298286be2d8ceacc426dedecc0e38a3f82d8aedc
                # Flatpak allows exporting empty Exec key because it is
                # going to be rewritten w/o command and command in
                # manifest is going to be used as default. Rely on
                # fallback but also warn
                if not len(exect) > 0:
                    self.warnings.add("desktop-file-exec-key-empty")
                # desktop files are rewritten only on (re)install, neither
                # exported ref or builddir should have "flatpak run"
                # unless manually added in desktop-file
                # https://github.com/flatpak/flatpak/blob/65bc369a9f7851cc1344d2a767b308050cd66fe3/common/flatpak-transaction.c#L4765
                # flatpak-dir.c: export_desktop_file < rewrite_export_dir
                # < flatpak_rewrite_export_dir < flatpak_dir_deploy
                # < flatpak_dir_deploy_install < flatpak_dir_install
                if len(exect) > 0 and "flatpak run" in exect:
                    self.errors.add("desktop-file-exec-has-flatpak-run")
            except KeyError:
                # https://gitlab.freedesktop.org/xdg/desktop-file-utils/-/issues/6
                self.errors.add("desktop-file-exec-key-absent")
                pass

            try:
                hidden = d["Desktop Entry"]["Hidden"]
                if hidden == "true":
                    self.errors.add("desktop-file-is-hidden")
            except KeyError:
                pass

            try:
                nodisplay = d["Desktop Entry"]["NoDisplay"]
                if nodisplay == "true":
                    self.errors.add("desktop-file-is-hidden")
            except KeyError:
                pass

            try:
                # https://github.com/ximion/appstream/blob/146099484012397f166cd428c56f230487b2d1fc/src/as-desktop-entry.c#L144-L154
                # appstreamcli filters these out during compose, "GUI"
                # is caught by desktop-file-validate
                block = {"KDE", "GTK", "Qt", "Application", "GNOME"}
                catgr: Set[str] = set(
                    filter(None, d["Desktop Entry"]["Categories"].split(";"))
                )
                if len(catgr) > 0 and catgr.issubset(block):
                    self.warnings.add("desktop-file-low-quality-category")
            except KeyError:
                pass

    def check_build(self, path: str) -> None:
        appid = builddir.infer_appid(path)
        if not appid:
            return
        metadata = builddir.get_metadata(path)
        if not metadata:
            return
        if metadata.get("extension"):
            return

        self._validate(f"{path}", appid)

    def check_repo(self, path: str) -> None:
        self._populate_ref(path)
        ref = self.repo_primary_ref
        if not ref:
            return
        appid = ref.split("/")[1]

        with tempfile.TemporaryDirectory() as tmpdir:
            ret = ostree.extract_subpath(path, ref, "/", tmpdir)
            if ret["returncode"] != 0:
                raise RuntimeError("Failed to extract ostree repo")
            self._validate(tmpdir, appid)
