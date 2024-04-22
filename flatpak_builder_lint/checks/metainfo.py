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
        glob_path = f"{icon_path}/*/apps/*"
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
            return

        metainfo_validation = appstream.validate(metainfo_path, "--no-net")
        if metainfo_validation["returncode"] != 0:
            self.errors.add("appstream-failed-validation")

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
            return

        if len(appstream.components(appstream_path)) != 1:
            self.errors.add("appstream-multiple-components")
            return

        if not appstream.is_valid_component_type(appstream_path):
            self.errors.add("appstream-unsupported-component-type")

        aps_cid = appstream.appstream_id(appstream_path)
        if aps_cid != appid:
            self.errors.add("appstream-id-mismatch-flatpak-id")

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
            if os.path.exists(icon_path):
                icon_list = [
                    os.path.basename(file)
                    for file in glob.glob(glob_path)
                    if re.match(rf"^{appid}([-.].*)?$", os.path.basename(file))
                    and os.path.isfile(file)
                ]
            else:
                icon_list = []
            if not len(icon_list) > 0:
                self.errors.add("no-exportable-icon-installed")

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
                return

            if launchable_file_path is not None and not os.path.exists(
                launchable_file_path
            ):
                self.errors.add("appstream-launchable-file-missing")
                return

            # the checks below depend on launchable being present

            if not appstream.is_categories_present(appstream_path):
                self.errors.add("appstream-missing-categories")

            icon_filename = appstream.get_icon_filename(appstream_path)
            appinfo_icon_path = f"{appinfo_icon_dir}/{icon_filename}"

            if not os.path.exists(appinfo_icon_path):
                self.errors.add("appstream-missing-icon-file")
            if not appstream.has_icon_key(appstream_path):
                self.errors.add("appstream-missing-icon-key")
                return
            if appstream.icon_no_type(appstream_path):
                self.errors.add("appstream-icon-key-no-type")
            if not appstream.is_remote_icon_mirrored(appstream_path):
                self.errors.add("appstream-remote-icon-not-mirrored")

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
