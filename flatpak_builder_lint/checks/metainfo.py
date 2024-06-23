import glob
import os
import re
import tempfile
from typing import List

from .. import appstream, builddir, ostree
from . import Check


class MetainfoCheck(Check):
    def _validate(self, path: str, appid: str) -> None:
        appstream_path = f"{path}/app-info/xmls/{appid}.xml.gz"
        appinfo_icon_dir = f"{path}/app-info/icons/flatpak/128x128/"
        launchable_dir = f"{path}/applications"
        icon_path = f"{path}/icons/hicolor"
        svg_icon_path = f"{icon_path}/scalable/apps"
        svg_glob_path = f"{icon_path}/scalable/apps/*"
        png_glob_path = f"{icon_path}/[!scalable]*/apps/*"
        metainfo_dirs = [
            f"{path}/metainfo",
            f"{path}/appdata",
        ]
        metainfo_exts = [".appdata.xml", ".metainfo.xml"]

        metainfo_path = None
        for metainfo_dir in metainfo_dirs:
            for ext in metainfo_exts:
                metainfo_dirext = f"{metainfo_dir}/{appid}{ext}"
                if os.path.exists(metainfo_dirext):
                    metainfo_path = metainfo_dirext

        if metainfo_path is None:
            self.errors.add("appstream-metainfo-missing")
            self.info.add(
                "appstream-metainfo-missing: No metainfo file was found in"
                + " /app/share/metainfo or /app/share/appdata"
            )
            return

        metainfo_validation = appstream.validate(metainfo_path, "--no-net")
        if metainfo_validation["returncode"] != 0:
            self.errors.add("appstream-failed-validation")
            self.info.add(
                "appstream-failed-validation: Metainfo file failed validation"
                + " Please see the errors in appstream block"
            )

            for err in metainfo_validation["stderr"].splitlines():
                self.appstream.add(err.strip())

            stdout: List[str] = list(
                filter(
                    lambda x: x.startswith(("E:", "W:")),
                    metainfo_validation["stdout"].splitlines()[:-1],
                )
            )
            for out in stdout:
                self.appstream.add(out.strip())

        component = appstream.parse_xml(metainfo_path).xpath("/component")

        if not component:
            self.errors.add("metainfo-missing-component-tag")
            return

        if component[0].attrib.get("type") is None:
            self.errors.add("metainfo-missing-component-type")

        if not os.path.exists(appstream_path):
            self.errors.add("appstream-missing-appinfo-file")
            self.info.add(
                "appstream-missing-appinfo-file: Appstream catalogue file is missing."
                + " Perhaps no Metainfo file was installed with correct name"
            )
            return

        if len(appstream.components(appstream_path)) != 1:
            self.errors.add("appstream-multiple-components")
            return

        if not appstream.is_valid_component_type(appstream_path):
            self.errors.add("appstream-unsupported-component-type")
            self.info.add(
                "appstream-unsupported-component-type: Component type must be one of"
                + " addon, console-application, desktop, desktop-application or runtime"
            )

        aps_cid = appstream.appstream_id(appstream_path)
        if aps_cid != appid:
            self.errors.add("appstream-id-mismatch-flatpak-id")
            self.info.add(
                f"appstream-id-mismatch-flatpak-id: The value of ID tag: {aps_cid} in Metainfo"
                + f" does not match the FLATPAK_ID: {appid}. Please see the docs for more details"
            )

        if appstream.component_type(appstream_path) not in (
            "desktop",
            "desktop-application",
            "console-application",
        ):
            return

        # for mypy
        name = appstream.name(appstream_path)
        summary = appstream.summary(appstream_path)

        if name is not None and len(name) > 20:
            self.warnings.add("appstream-name-too-long")
        if summary is not None:
            if len(summary) > 35:
                self.warnings.add("appstream-summary-too-long")
            if summary.endswith("."):
                self.warnings.add("appstream-summary-ends-in-dot")

        if not appstream.is_developer_name_present(appstream_path):
            self.errors.add("appstream-missing-developer-name")
        if not appstream.is_project_license_present(appstream_path):
            self.errors.add("appstream-missing-project-license")

        if not appstream.check_caption(appstream_path):
            self.warnings.add("appstream-screenshot-missing-caption")

        if appstream.component_type(appstream_path) in (
            "desktop",
            "desktop-application",
        ):
            svg_icon_list = []
            wrong_svgs = []
            if os.path.exists(svg_icon_path):
                svg_icon_list = [
                    file
                    for file in glob.glob(svg_glob_path)
                    if re.match(rf"^{appid}([-.].*)?$", os.path.basename(file))
                    and os.path.isfile(file)
                ]
                wrong_svgs = [
                    i for i in svg_icon_list if not i.endswith((".svg", ".svgz"))
                ]
            if not all(i.endswith((".svg", ".svgz")) for i in svg_icon_list):
                self.errors.add("non-svg-icon-in-scalable-folder")
                self.info.add(f"non-svg-icon-in-scalable-folder: {wrong_svgs}")

            png_icon_list = []
            wrong_pngs = []
            if os.path.exists(icon_path):
                png_icon_list = [
                    file
                    for file in glob.glob(png_glob_path)
                    if re.match(rf"^{appid}([-.].*)?$", os.path.basename(file))
                    and os.path.isfile(file)
                ]
                wrong_pngs = [i for i in png_icon_list if not i.endswith(".png")]
            if not all(i.endswith(".png") for i in png_icon_list):
                self.errors.add("non-png-icon-in-hicolor-size-folder")
                self.info.add(f"non-png-icon-in-hicolor-size-folder: {wrong_pngs}")
            icon_list = svg_icon_list + png_icon_list
            if not len(icon_list) > 0:
                self.errors.add("no-exportable-icon-installed")
                self.info.add(
                    "no-exportable-icon-installed: No PNG or SVG icons named by FLATPAK_ID"
                    + " were found in /app/share/icons/hicolor/$size/apps"
                    + " or /app/share/icons/hicolor/scalable/apps"
                )

            if not appstream.get_launchable(appstream_path):
                self.errors.add("metainfo-missing-launchable-tag")

            if appstream.get_launchable(appstream_path):
                launchable_value = appstream.get_launchable(appstream_path)[0]
                launchable_file_path = f"{launchable_dir}/{launchable_value}"
            else:
                launchable_value = None
                launchable_file_path = None

            # Don't allow all exportable combinations to avoid issues
            # like typos. This must match the main desktop file named by
            # appid.desktop and must not have multiple launchables in
            # metainfo per the spec
            if launchable_value is not None and launchable_value != appid + ".desktop":
                self.errors.add("metainfo-launchable-tag-wrong-value")
                self.info.add(
                    "metainfo-launchable-tag-wrong-value: The value of launchable tag in Metainfo"
                    + f" is wrong: {launchable_value}"
                )
                return

            if launchable_file_path is not None and not os.path.exists(
                launchable_file_path
            ):
                self.errors.add("appstream-launchable-file-missing")
                self.info.add(
                    f"appstream-launchable-file-missing: The launchable file {launchable_value}"
                    + " was not found in /app/share/applications"
                )
                return

            # the checks below depend on launchable being present

            if not appstream.is_categories_present(appstream_path):
                self.errors.add("appstream-missing-categories")
                self.info.add(
                    "appstream-missing-categories: The catalogue file is missing categories"
                    + " Perhaps low quality categories were filtered or"
                    + " none were found in desktop file"
                )

            icon_filename = appstream.get_icon_filename(appstream_path)
            appinfo_icon_path = f"{appinfo_icon_dir}/{icon_filename}"

            if not os.path.exists(appinfo_icon_path):
                self.errors.add("appstream-missing-icon-file")
                self.info.add(
                    "appstream-missing-icon-file: No icon was generated by appstream."
                    + " Perhaps a >=128px PNG or SVG was not installed correctly"
                )
                return
            if not appstream.has_icon_key(appstream_path):
                self.errors.add("appstream-missing-icon-key")
                return
            if appstream.icon_no_type(appstream_path):
                self.errors.add("appstream-icon-key-no-type")
            if not appstream.is_remote_icon_mirrored(appstream_path):
                self.errors.add("appstream-remote-icon-not-mirrored")
                self.info.add(
                    "appstream-remote-icon-not-mirrored: Remote icons are not mirrored to Flathub"
                    + " Please see the docs for more information"
                )

    def check_build(self, path: str) -> None:
        appid = builddir.infer_appid(path)
        if not appid:
            return
        if appid.endswith(".BaseApp"):
            return
        metadata = builddir.parse_metadata(path)
        if not metadata:
            return
        if metadata.get("type", False) != "application":
            return

        self._validate(f"{path}/files/share", appid)

    def check_repo(self, path: str) -> None:
        self._populate_ref(path)
        ref = self.repo_primary_ref
        if not ref:
            return
        appid = ref.split("/")[1]

        if appid.endswith(".BaseApp"):
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            retm = ostree.extract_subpath(path, ref, "/metadata", tmpdir)
            if retm["returncode"] != 0:
                raise RuntimeError("Failed to extract ostree repo")
            metadata = builddir.parse_metadata(tmpdir)
            if not metadata:
                return
            if metadata.get("type", False) != "application":
                return

            ret = ostree.extract_subpath(path, ref, "files/share", tmpdir)
            if ret["returncode"] != 0:
                raise RuntimeError("Failed to extract ostree repo")

            self._validate(tmpdir, appid)
