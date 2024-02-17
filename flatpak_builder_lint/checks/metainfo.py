import glob
import os
import re
import tempfile
from typing import List

from .. import appstream, builddir, ostree
from . import Check


class MetainfoCheck(Check):
    def _validate(self, path: str, appid: str) -> None:
        appstream_path = f"{path}/files/share/app-info/xmls/{appid}.xml.gz"
        appinfo_icon_dir = f"{path}/files/share/app-info/icons/flatpak/128x128/"
        icon_path = f"{path}/files/share/icons/hicolor"
        glob_path = f"{icon_path}/*/apps/*"
        metainfo_dirs = [
            f"{path}/files/share/metainfo",
            f"{path}/files/share/appdata",
        ]
        metainfo_exts = [".appdata.xml", ".metainfo.xml"]

        if appid.endswith(".BaseApp"):
            return

        metainfo_path = None
        for metainfo_dir in metainfo_dirs:
            for ext in metainfo_exts:
                metainfo_dirext = f"{metainfo_dir}/{appid}{ext}"
                if os.path.exists(metainfo_dirext):
                    metainfo_path = metainfo_dirext

        if metainfo_path is None:
            return

        if not os.path.exists(metainfo_path):
            self.errors.add("appstream-metainfo-missing")
            return

        metainfo_validation = appstream.validate(metainfo_path)
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

        if appstream.component_type(appstream_path) not in (
            "desktop",
            "desktop-application",
            "console-application",
        ):
            return

        if appstream.component_type(appstream_path) in (
            "desktop",
            "desktop-application",
        ):
            icon_filename = appstream.get_icon_filename(appstream_path)
            appinfo_icon_path = f"{appinfo_icon_dir}/{icon_filename}"

            if not os.path.exists(appinfo_icon_path):
                self.errors.add("appstream-missing-icon-file")

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

        if not appstream.is_developer_name_present(appstream_path):
            self.errors.add("appstream-missing-developer-name")
        if not appstream.is_project_license_present(appstream_path):
            self.errors.add("appstream-missing-project-license")

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

    # https://github.com/flathub-infra/flatpak-builder-lint/issues/280
    #        if not appstream.check_caption(appstream_path):
    #            self.warnings.add("appstream-screenshot-missing-caption")

    def check_build(self, path: str) -> None:
        appid = builddir.infer_appid(path)
        if not appid:
            return
        metadata = builddir.get_metadata(path)
        if not metadata:
            return
        if metadata.get("type", False) != "application":
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
